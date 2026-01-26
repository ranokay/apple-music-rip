import {
	type ChildProcessWithoutNullStreams,
	spawn,
	spawnSync,
} from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { readdir, stat } from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import readline from "node:readline";
import { staticPlugin } from "@elysiajs/static";
import { Elysia } from "elysia";
import yaml from "js-yaml";

const SURVEY_REPLACE_FLAG =
	"-mod=mod -replace=github.com/AlecAivazis/survey/v2=../wrapper/survey_stub";

const WEB_ROOT = path.resolve(import.meta.dir, "..");
const REPO_ROOT = path.resolve(import.meta.dir, "../../..");
const APPS_ROOT = path.join(REPO_ROOT, "apps");
const AMD_DIR = path.join(APPS_ROOT, "apple-music-downloader");
const CONFIG_PATH = path.join(AMD_DIR, "config.yaml");
const DOWNLOAD_HISTORY_FILE = path.join(APPS_ROOT, "download_history.json");
const DIST_DIR = path.join(WEB_ROOT, "dist");

const DEFAULT_BROWSE_DIR =
	process.env.AMR_DEFAULT_DIR || path.join(os.homedir(), "Downloads");

const app = new Elysia();

let wrapperRunning = false;
const wrapperLogs: string[] = [];
const downloaderLogs: string[] = [];
let downloadProcess: ChildProcessWithoutNullStreams | null = null;
let downloadRunning = false;
let lastWrapperLogCount = 0;
let lastDownloadMilestone = -1;
let lastDecryptMilestone = -1;
let currentProgress = { label: "", percent: 0, details: "" };
let downloadHistoryEntries: Array<{
	artist: string;
	album: string;
	release_type: string;
	album_id: string;
	track_num: number;
	track_name: string;
	storefront: string;
	formats: string[];
}> = [];

function appendLog(list: string[], line: string) {
	list.push(line);
	if (list.length > 2000) {
		list.splice(0, list.length - 2000);
	}
}

function loadDownloadHistory() {
	if (existsSync(DOWNLOAD_HISTORY_FILE)) {
		try {
			const raw = readFileSync(DOWNLOAD_HISTORY_FILE, "utf-8");
			return JSON.parse(raw);
		} catch {
			return { artists: {} };
		}
	}
	return { artists: {} };
}

function saveDownloadHistory(history: Record<string, unknown>) {
	try {
		writeFileSync(
			DOWNLOAD_HISTORY_FILE,
			JSON.stringify(history, null, 2),
			"utf-8",
		);
		return true;
	} catch (error) {
		console.error("Error saving download history:", error);
		return false;
	}
}

function addToDownloadHistory(
	artist: string,
	title: string,
	releaseType: string,
	link: string,
	tracks: number[],
	formats: string[],
) {
	const history = loadDownloadHistory();

	let releaseKey = releaseType.toLowerCase();
	if (!releaseKey.endsWith("s")) releaseKey += "s";

	if (!history.artists) history.artists = {};
	if (!history.artists[artist]) {
		history.artists[artist] = {
			albums: [],
			eps: [],
			singles: [],
		};
	}

	if (!history.artists[artist][releaseKey]) {
		history.artists[artist][releaseKey] = [];
	}

	const existingReleases = history.artists[artist][releaseKey] ?? [];
	let found = false;

	for (const release of existingReleases) {
		if (release.link === link) {
			const existingTracks = new Set<number>(release.tracks ?? []);
			tracks.forEach((track) => existingTracks.add(track));
			release.tracks = Array.from(existingTracks).sort((a, b) => a - b);

			const existingFormats = new Set<string>(release.formats ?? []);
			formats.forEach((format) => existingFormats.add(format));
			release.formats = Array.from(existingFormats);

			release.last_updated = new Date().toISOString();
			found = true;
			break;
		}
	}

	if (!found) {
		const entry = {
			name: title,
			link,
			tracks: tracks.slice().sort((a, b) => a - b),
			formats,
			date_added: new Date().toISOString(),
			last_updated: new Date().toISOString(),
		};
		history.artists[artist][releaseKey].push(entry);
	}

	saveDownloadHistory(history);
	return true;
}

function processHistoryEntry(line: string, formats: string[]) {
	if (!line.startsWith("HISTORY:")) return false;

	try {
		const jsonStr = line.slice(8);
		const entry = JSON.parse(jsonStr);
		if (entry?._history_entry !== "download") return false;

		downloadHistoryEntries.push({
			artist: entry.artist ?? "Unknown Artist",
			album: entry.album ?? "Unknown Album",
			release_type: entry.release_type ?? "Albums",
			album_id: entry.album_id ?? "",
			track_num: entry.track_num ?? 1,
			track_name: entry.track_name ?? "",
			storefront: entry.storefront ?? "us",
			formats,
		});

		return true;
	} catch {
		return false;
	}
}

function saveCollectedHistoryEntries() {
	if (downloadHistoryEntries.length === 0) return;

	const grouped = new Map<
		string,
		{
			artist: string;
			album: string;
			release_type: string;
			album_id: string;
			storefront: string;
			tracks: Set<number>;
			formats: Set<string>;
		}
	>();

	for (const entry of downloadHistoryEntries) {
		const key = `${entry.artist}__${entry.album}__${entry.release_type}__${entry.album_id}`;
		if (!grouped.has(key)) {
			grouped.set(key, {
				artist: entry.artist,
				album: entry.album,
				release_type: entry.release_type,
				album_id: entry.album_id,
				storefront: entry.storefront,
				tracks: new Set<number>(),
				formats: new Set<string>(),
			});
		}
		const group = grouped.get(key)!;
		group.tracks.add(entry.track_num);
		entry.formats.forEach((format) => group.formats.add(format));
	}

	grouped.forEach((data) => {
		const link = data.album_id
			? `https://music.apple.com/${data.storefront}/album/${data.album_id}`
			: `unknown://${data.artist}/${data.album}`;

		addToDownloadHistory(
			data.artist,
			data.album,
			data.release_type,
			link,
			Array.from(data.tracks),
			Array.from(data.formats),
		);
	});

	downloadHistoryEntries = [];
}

function getWrapperLogs() {
	try {
		const result = spawnSync("docker", ["logs", "wrapper-runtime"], {
			encoding: "utf-8",
			timeout: 5000,
		});

		if (result.error?.name === "ETIMEDOUT") {
			appendLog(wrapperLogs, "⚠️ Timeout getting wrapper logs");
			return false;
		}

		if (result.stdout) {
			const allLines = result.stdout.trim().split("\n");
			if (allLines.length > lastWrapperLogCount) {
				const newLines = allLines.slice(lastWrapperLogCount);
				newLines.forEach((line) => {
					if (line.trim()) appendLog(wrapperLogs, line.trim());
				});
				lastWrapperLogCount = allLines.length;
			}
		}

		return true;
	} catch {
		return false;
	}
}

function wrapperHostPort() {
	let host = "127.0.0.1";
	let port = 10020;

	try {
		if (existsSync(CONFIG_PATH)) {
			const raw = readFileSync(CONFIG_PATH, "utf-8");
			const config = (yaml.load(raw) as Record<string, unknown>) || {};
			const value = config["decrypt-m3u8-port"];
			if (typeof value === "string" && value.includes(":")) {
				const [h, p] = value.split(":", 2);
				host = h || host;
				const parsed = Number.parseInt(p ?? "", 10);
				if (!Number.isNaN(parsed)) port = parsed;
			}
		}
	} catch (error) {
		appendLog(
			wrapperLogs,
			`⚠️ Could not read config.yaml for wrapper port: ${error}`,
		);
	}

	return { host, port };
}

function checkWrapperRunning() {
	const { host, port } = wrapperHostPort();

	return new Promise<boolean>((resolve) => {
		const socket = net.createConnection({ host, port });
		const finish = (value: boolean) => {
			socket.removeAllListeners();
			socket.end();
			resolve(value);
		};

		socket.setTimeout(1000);
		socket.on("connect", () => finish(true));
		socket.on("timeout", () => finish(false));
		socket.on("error", () => finish(false));
	});
}

function parseProgressLine(line: string) {
	const trackMatch = line.match(/Track (\d+) of (\d+)/);
	if (trackMatch) {
		const current = Number.parseInt(trackMatch[1], 10);
		const total = Number.parseInt(trackMatch[2], 10);
		const percent = total > 0 ? (current / total) * 100 : 0;
		currentProgress = {
			label: `📦 Track ${current} of ${total}`,
			percent,
			details: "",
		};
		lastDownloadMilestone = -1;
		lastDecryptMilestone = -1;
		return null;
	}

	const downloadMatch = line.match(/Downloading\.\.\.\s+(\d+)%/);
	if (downloadMatch) {
		const percent = Number.parseInt(downloadMatch[1], 10);
		currentProgress.details = `⬇️ Downloading... ${percent}%`;
		const milestone = Math.floor(percent / 25) * 25;
		if (milestone > lastDownloadMilestone) {
			lastDownloadMilestone = milestone;
			return ["download", percent] as const;
		}
		return null;
	}

	if (line.includes("Downloaded")) {
		currentProgress.details = "⬇️ Downloaded";
		lastDownloadMilestone = 100;
		return ["download_done", 100] as const;
	}

	const decryptMatch = line.match(/Decrypting\.\.\.\s+(\d+)%/);
	if (decryptMatch) {
		const percent = Number.parseInt(decryptMatch[1], 10);
		currentProgress.details = `🔓 Decrypting... ${percent}%`;
		const milestone = Math.floor(percent / 25) * 25;
		if (milestone > lastDecryptMilestone) {
			lastDecryptMilestone = milestone;
			return ["decrypt", percent] as const;
		}
		return null;
	}

	if (line.includes("Decrypted")) {
		currentProgress.details = "🔓 Decrypted";
		lastDecryptMilestone = 100;
		return ["decrypt_done", 100] as const;
	}

	if (line.includes("Converting")) {
		currentProgress.details = "🔄 Converting to FLAC...";
		return null;
	}

	if (line.includes("completed successfully")) {
		currentProgress = { label: "✅ Completed", percent: 100, details: "" };
	}

	return null;
}

function cleanLogLine(line: string) {
	let cleaned = line.replace(/\x1b\[[0-9;]*m/g, "");
	cleaned = cleaned.replace(/\r/g, "");
	return cleaned.trim();
}

function isProgressNoise(line: string) {
	if (/^\s*[\d.]+\s*(MB|KB|GB|%|\/)\s*$/i.test(line)) return true;
	if (line.length > 50 && (line.match(/ /g) || []).length > 30) return true;
	return false;
}

function updateConfigForFormat(
	formatChoice: string,
	downloadMode: string,
	isAtmos: boolean,
) {
	try {
		if (existsSync(CONFIG_PATH)) {
			const raw = readFileSync(CONFIG_PATH, "utf-8");
			const config = (yaml.load(raw) as Record<string, unknown>) || {};

			if (formatChoice === "hires") {
				config["get-m3u8-mode"] = "hires";
			} else {
				config["get-m3u8-mode"] = "web";
			}

			if (isAtmos) {
				config["convert-after-download"] = false;
				config["save-animated-artwork"] = true;
			} else {
				config["convert-after-download"] = true;
				config["convert-format"] = "flac";
				config["convert-keep-original"] = false;
				config["save-animated-artwork"] = false;
			}

			writeFileSync(CONFIG_PATH, yaml.dump(config, { indent: 2 }), "utf-8");

			let saveFolder = "";
			if (downloadMode === "lyrics") {
				saveFolder =
					(config["alac-save-folder"] as string) || "AM-DL downloads";
			} else if (downloadMode === "covers") {
				saveFolder =
					(config["alac-save-folder"] as string) || "AM-DL downloads";
			} else if (formatChoice === "atmos") {
				saveFolder =
					(config["atmos-save-folder"] as string) || "AM-DL-Atmos downloads";
			} else if (formatChoice === "aac") {
				saveFolder =
					(config["aac-save-folder"] as string) || "AM-DL-AAC downloads";
			} else {
				saveFolder =
					(config["alac-save-folder"] as string) || "AM-DL downloads";
			}

			appendLog(downloaderLogs, `💾 Download will be saved to: ${saveFolder}`);
		}
	} catch (error) {
		console.error("Error reading/writing config:", error);
		appendLog(downloaderLogs, `⚠️ Error updating config: ${error}`);
	}
}

async function runSingleDownload(
	link: string,
	formatChoice: string,
	downloadMode: string,
	selectedTracks: string,
	isAtmos: boolean,
) {
	updateConfigForFormat(formatChoice, downloadMode, isAtmos);

	let cmd = ["go", "run", "main.go", link];

	if (downloadMode === "lyrics") {
		cmd = ["go", "run", "main.go", "--lyrics-only", link];
		appendLog(downloaderLogs, `🎵 Starting lyrics-only download: ${link}`);
	} else if (downloadMode === "covers") {
		cmd = ["go", "run", "main.go", "--covers-only", link];
		appendLog(downloaderLogs, `🎵 Starting covers-only download: ${link}`);
	} else if (formatChoice === "atmos") {
		cmd = ["go", "run", "main.go", "--atmos", link];
		appendLog(downloaderLogs, `🎵 Starting ATMOS download: ${link}`);
	} else if (formatChoice === "aac") {
		cmd = ["go", "run", "main.go", "--aac", link];
		appendLog(downloaderLogs, `🎵 Starting AAC download: ${link}`);
	} else if (formatChoice === "hires") {
		appendLog(downloaderLogs, `🎵 Starting Hi-Res Lossless download: ${link}`);
	} else {
		appendLog(downloaderLogs, `🎵 Starting Lossless download: ${link}`);
	}

	if (selectedTracks) {
		cmd = [
			cmd[0],
			cmd[1],
			cmd[2],
			"--select-tracks",
			selectedTracks,
			...cmd.slice(3),
		];
		appendLog(downloaderLogs, `✅ Selected tracks: ${selectedTracks}`);
	}

	appendLog(downloaderLogs, `📁 Working directory: ${AMD_DIR}`);
	appendLog(downloaderLogs, `⚡ Executing: ${cmd.join(" ")}`);

	const env = { ...process.env } as Record<string, string>;
	const goflags = (env.GOFLAGS || "").trim();
	if (!goflags.includes(SURVEY_REPLACE_FLAG)) {
		env.GOFLAGS = `${goflags} ${SURVEY_REPLACE_FLAG}`.trim();
	}

	try {
		downloadProcess = spawn(cmd[0], cmd.slice(1), {
			cwd: AMD_DIR,
			env,
			detached: true,
			stdio: ["ignore", "pipe", "pipe"],
		});

		const runningProcess = downloadProcess;
		if (!runningProcess) {
			appendLog(
				downloaderLogs,
				`❌ ${formatChoice.toUpperCase()} download failed to start.`,
			);
			return false;
		}

		const closePromise = new Promise<number | null>((resolve) =>
			runningProcess.once("close", resolve),
		);

		const consume = async (stream: NodeJS.ReadableStream | null) => {
			if (!stream) return;
			const rl = readline.createInterface({ input: stream });
			for await (const rawLine of rl) {
				const cleanLine = cleanLogLine(String(rawLine));
				if (!cleanLine) continue;
				if (isProgressNoise(cleanLine)) continue;

				if (cleanLine.startsWith("HISTORY:")) {
					const entryFormats = isAtmos
						? ["atmos"]
						: formatChoice === "aac"
							? ["aac"]
							: formatChoice === "hires"
								? ["hires"]
								: ["lossless"];
					processHistoryEntry(cleanLine, entryFormats);
					continue;
				}

				if (/\b(Downloading|Decrypting)\.\.\.\s+\d+%/.test(cleanLine)) {
					const milestone = parseProgressLine(cleanLine);
					if (milestone) {
						const [action, percent] = milestone;
						if (action === "download") {
							const msg = `⬇️ Downloading... ${percent}%`;
							appendLog(downloaderLogs, msg);
						} else if (action === "decrypt") {
							const msg = `🔓 Decrypting... ${percent}%`;
							appendLog(downloaderLogs, msg);
						}
					}
					continue;
				}

				appendLog(downloaderLogs, cleanLine);
				parseProgressLine(cleanLine);
			}
		};

		await Promise.all([
			consume(runningProcess.stdout),
			consume(runningProcess.stderr),
		]);
		const exitCode = await closePromise;

		if (exitCode === 0) {
			appendLog(
				downloaderLogs,
				`✅ ${formatChoice.toUpperCase()} download completed!`,
			);
			return true;
		}

		appendLog(
			downloaderLogs,
			`❌ ${formatChoice.toUpperCase()} download failed with exit code: ${exitCode}`,
		);
		return false;
	} catch (error) {
		appendLog(
			downloaderLogs,
			`❌ Error during ${formatChoice} download: ${error}`,
		);
		return false;
	} finally {
		downloadProcess = null;
	}
}

async function runMultiDownload(
	link: string,
	formats: string[],
	downloadMode: string,
	selectedTracks: string,
	metadata: Record<string, unknown> | null,
) {
	const sortedFormats = [...formats].sort((a, b) =>
		a === "atmos" ? -1 : b === "atmos" ? 1 : 0,
	);
	const totalFormats = sortedFormats.length;

	appendLog(
		downloaderLogs,
		`📦 Starting multi-format download (${totalFormats} formats): ${sortedFormats.join(", ")}`,
	);

	let anySuccess = false;

	for (let i = 0; i < sortedFormats.length; i += 1) {
		if (!downloadRunning) {
			appendLog(downloaderLogs, "🛑 Download stopped by user");
			break;
		}

		const fmt = sortedFormats[i];
		appendLog(downloaderLogs, `\n${"=".repeat(50)}`);
		appendLog(
			downloaderLogs,
			`📥 Format ${i + 1}/${totalFormats}: ${fmt.toUpperCase()}`,
		);
		appendLog(downloaderLogs, "=".repeat(50));

		currentProgress = {
			label: `Format ${i + 1}/${totalFormats}: ${fmt.toUpperCase()}`,
			percent: (i / totalFormats) * 100,
			details: "Starting...",
		};

		const isAtmos = fmt === "atmos";
		const success = await runSingleDownload(
			link,
			fmt,
			downloadMode,
			selectedTracks,
			isAtmos,
		);

		if (success) {
			anySuccess = true;
		} else {
			appendLog(
				downloaderLogs,
				`⚠️ ${fmt.toUpperCase()} download had issues, continuing with next format...`,
			);
		}
	}

	if (anySuccess && downloadMode === "audio") {
		saveCollectedHistoryEntries();
		appendLog(downloaderLogs, "📝 Download history updated");
	}

	downloadRunning = false;
	currentProgress = {
		label: "✅ All downloads completed",
		percent: 100,
		details: "",
	};
	appendLog(downloaderLogs, "\n✅ All format downloads completed!");

	return metadata;
}

function translatePathToWsl(value: string) {
	if (!value) return value;
	if (value.length >= 3 && value[1] === ":" && value[2] === "\\") {
		const drive = value[0].toLowerCase();
		const rest = value.slice(3).replace(/\\/g, "/");
		return `/mnt/${drive}/${rest}`;
	}
	if (value.length >= 3 && value[1] === ":" && value[2] === "/") {
		const drive = value[0].toLowerCase();
		const rest = value.slice(3);
		return `/mnt/${drive}/${rest}`;
	}
	return value;
}

async function listDirectories(dirPath: string) {
	const entries = await readdir(dirPath, { withFileTypes: true });
	return entries
		.filter((entry) => entry.isDirectory())
		.map((entry) => ({
			name: entry.name,
			path: path.join(dirPath, entry.name),
		}))
		.sort((a, b) => a.name.localeCompare(b.name));
}

async function resolveBrowsePath(rawPath?: string) {
	let candidate = rawPath?.trim();
	if (candidate?.startsWith("~")) {
		candidate = path.join(os.homedir(), candidate.slice(1));
	}
	const resolved = candidate
		? path.isAbsolute(candidate)
			? path.resolve(candidate)
			: path.resolve(DEFAULT_BROWSE_DIR, candidate)
		: DEFAULT_BROWSE_DIR;
	try {
		const stats = await stat(resolved);
		if (stats.isDirectory()) return resolved;
	} catch {
		// fallback below
	}

	try {
		const fallbackStats = await stat(DEFAULT_BROWSE_DIR);
		if (fallbackStats.isDirectory()) return DEFAULT_BROWSE_DIR;
	} catch {
		// fall through
	}

	throw new Error("Path is not a directory");
}

async function runCommand(
	cmd: string[],
	options: Record<string, unknown>,
	timeoutMs: number,
) {
	return new Promise<{ code: number | null; stdout: string; stderr: string }>(
		(resolve, reject) => {
			const child = spawn(cmd[0], cmd.slice(1), options);
			let stdout = "";
			let stderr = "";

			const timer = setTimeout(() => {
				child.kill("SIGKILL");
				reject(new Error("timeout"));
			}, timeoutMs);

			child.stdout?.on("data", (chunk) => {
				stdout += chunk.toString();
			});
			child.stderr?.on("data", (chunk) => {
				stderr += chunk.toString();
			});

			child.on("error", (error) => {
				clearTimeout(timer);
				reject(error);
			});

			child.on("close", (code) => {
				clearTimeout(timer);
				resolve({ code, stdout, stderr });
			});
		},
	);
}

app
	.get("/api/get-logs", async () => {
		getWrapperLogs();
		wrapperRunning = await checkWrapperRunning();

		if (downloadProcess && downloadProcess.exitCode !== null) {
			downloadRunning = false;
		}

		return {
			wrapper: wrapperLogs.slice(-200),
			downloader: downloaderLogs.slice(-200),
			wrapper_running: wrapperRunning,
			download_running: downloadRunning,
			progress: currentProgress,
		};
	})
	.post("/api/preview", async ({ body }) => {
		const link = (body as Record<string, string> | undefined)?.link?.trim();
		if (!link) {
			return { status: "error", msg: "No URL provided" };
		}

		wrapperRunning = await checkWrapperRunning();
		if (!wrapperRunning) {
			return { status: "error", msg: "Wrapper not reachable" };
		}

		const env = { ...process.env } as Record<string, string>;
		const goflags = (env.GOFLAGS || "").trim();
		if (!goflags.includes(SURVEY_REPLACE_FLAG)) {
			env.GOFLAGS = `${goflags} ${SURVEY_REPLACE_FLAG}`.trim();
		}

		try {
			const result = await runCommand(
				["go", "run", "main.go", "--preview", link],
				{
					cwd: AMD_DIR,
					env,
				},
				60_000,
			);

			const stdout = result.stdout.trim();
			const stderr = result.stderr.trim();

			if (result.code !== 0) {
				return {
					status: "error",
					msg:
						stderr || stdout || `Preview failed with exit code ${result.code}`,
				};
			}

			if (!stdout) {
				return { status: "error", msg: "Preview returned no data" };
			}

			const data = JSON.parse(stdout);
			return { status: "ok", data };
		} catch (error) {
			if ((error as Error).message === "timeout") {
				return { status: "error", msg: "Preview timed out" };
			}
			return { status: "error", msg: String(error) };
		}
	})
	.post("/api/download", async ({ body }) => {
		const payload = body as Record<string, unknown> | undefined;
		const link = (payload?.link as string | undefined)?.trim() || "";
		const mode = (payload?.mode as string | undefined) || "audio";
		const selectedTracks = (payload?.select_tracks as string | undefined) || "";

		const rawFormats = payload?.formats;
		const formats = Array.isArray(rawFormats)
			? rawFormats.map((format) => String(format))
			: typeof rawFormats === "string"
				? rawFormats
						.split(",")
						.map((format) => format.trim())
						.filter(Boolean)
				: [];

		const metadata = {
			artist: (payload?.artist as string | undefined) || "",
			title: (payload?.title as string | undefined) || "",
			release_type: (payload?.release_type as string | undefined) || "Albums",
			track_count: Number(payload?.track_count ?? 1),
		};

		wrapperRunning = await checkWrapperRunning();
		if (!wrapperRunning) {
			return { status: "error", msg: "Wrapper not reachable" };
		}

		if (downloadRunning) {
			return { status: "error", msg: "Download already in progress" };
		}

		if (!link) {
			return { status: "error", msg: "No URL provided" };
		}

		const formatsList = formats.length > 0 ? formats : ["lossless"];

		currentProgress = { label: "Starting...", percent: 0, details: "" };
		downloadRunning = true;

		runMultiDownload(link, formatsList, mode, selectedTracks, metadata).catch(
			(error) => {
				appendLog(downloaderLogs, `❌ Download error: ${error}`);
				downloadRunning = false;
			},
		);

		return {
			status: "ok",
			msg: `Download started for formats: ${formatsList.join(", ")}`,
		};
	})
	.post("/api/stop-download", async () => {
		if (!downloadRunning || !downloadProcess) {
			return { status: "error", msg: "No download in progress" };
		}

		try {
			const stopFilePath = path.join(AMD_DIR, "stop.signal");
			writeFileSync(stopFilePath, "stop", "utf-8");
			appendLog(downloaderLogs, "🛑 Stop signal sent to downloader");

			try {
				process.kill(-downloadProcess.pid, "SIGKILL");
				appendLog(downloaderLogs, "🛑 Download killed");
			} catch {
				try {
					downloadProcess.kill("SIGKILL");
					appendLog(downloaderLogs, "🛑 Download killed (fallback)");
				} catch {
					appendLog(downloaderLogs, "⚠️ Failed to kill download process");
				}
			}

			downloadRunning = false;
			downloadProcess = null;

			return { status: "ok", msg: "Download stopped successfully" };
		} catch (error) {
			appendLog(downloaderLogs, `❌ Error stopping download: ${error}`);
			return { status: "error", msg: `Failed to stop download: ${error}` };
		}
	})
	.get("/api/get-config", () => {
		try {
			const raw = readFileSync(CONFIG_PATH, "utf-8");
			const config = yaml.load(raw) as Record<string, unknown>;
			return { status: "ok", config };
		} catch (error) {
			return { status: "error", msg: String(error) };
		}
	})
	.post("/api/save-config", ({ body }) => {
		try {
			const configData = (body as Record<string, unknown>) ?? {};

			const integerFields = new Set([
				"alac-max",
				"atmos-max",
				"limit-max",
				"max-memory-limit",
				"mv-max",
			]);

			const booleanFields = new Set([
				"embed-lrc",
				"save-lrc-file",
				"save-artist-cover",
				"save-animated-artwork",
				"emby-animated-artwork",
				"embed-cover",
				"get-m3u8-from-device",
				"use-songinfo-for-playlist",
				"dl-albumcover-for-playlist",
				"convert-after-download",
				"convert-keep-original",
				"convert-skip-if-source-matches",
			]);

			const pathFields = new Set([
				"alac-save-folder",
				"atmos-save-folder",
				"aac-save-folder",
			]);

			Object.entries(configData).forEach(([key, value]) => {
				if (integerFields.has(key)) {
					const parsed = Number.parseInt(String(value ?? ""), 10);
					configData[key] = Number.isNaN(parsed) ? 0 : parsed;
				} else if (booleanFields.has(key)) {
					if (typeof value === "string") {
						configData[key] = ["true", "1", "yes", "on"].includes(
							value.toLowerCase(),
						);
					} else {
						configData[key] = Boolean(value);
					}
				} else if (pathFields.has(key)) {
					configData[key] = translatePathToWsl(String(value ?? ""));
				}
			});

			writeFileSync(CONFIG_PATH, yaml.dump(configData, { indent: 2 }), "utf-8");

			return { status: "ok", msg: "Configuration saved successfully" };
		} catch (error) {
			return { status: "error", msg: String(error) };
		}
	})
	.get("/api/get-download-folders", () => {
		try {
			const raw = readFileSync(CONFIG_PATH, "utf-8");
			const config = (yaml.load(raw) as Record<string, unknown>) || {};

			return {
				status: "ok",
				folders: {
					alac: (config["alac-save-folder"] as string) || "AM-DL downloads",
					atmos:
						(config["atmos-save-folder"] as string) || "AM-DL-Atmos downloads",
					aac: (config["aac-save-folder"] as string) || "AM-DL-AAC downloads",
				},
			};
		} catch (error) {
			return { status: "error", msg: String(error) };
		}
	})
	.get("/api/get-download-history", () => {
		try {
			const history = loadDownloadHistory();
			return { status: "ok", history };
		} catch (error) {
			return { status: "error", msg: String(error) };
		}
	})
	.get("/api/fs", async ({ query }) => {
		const requested = typeof query?.path === "string" ? query.path : undefined;
		try {
			const resolved = await resolveBrowsePath(requested);
			const entries = await listDirectories(resolved);
			const root = path.parse(resolved).root;
			const parent = resolved === root ? null : path.dirname(resolved);
			return { status: "ok", path: resolved, parent, entries };
		} catch (error) {
			if (!requested) {
				try {
					const fallback = path.resolve(os.homedir());
					const entries = await listDirectories(fallback);
					const root = path.parse(fallback).root;
					const parent = fallback === root ? null : path.dirname(fallback);
					return { status: "ok", path: fallback, parent, entries };
				} catch {
					// ignore fallback errors
				}
			}
			return { status: "error", msg: String(error) };
		}
	});

if (existsSync(DIST_DIR)) {
	app.get("/", () => Bun.file(path.join(DIST_DIR, "index.html")));
	app.get("/settings", () =>
		Bun.file(path.join(DIST_DIR, "settings", "index.html")),
	);
	app.use(staticPlugin({ assets: DIST_DIR, prefix: "" }));
}

const port = Number.parseInt(process.env.PORT || "3001", 10);
app.listen(port);

console.log(`Elysia server running on http://localhost:${port}`);
