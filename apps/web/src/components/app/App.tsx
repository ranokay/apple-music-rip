import {
	Download,
	FolderOpen,
	Info,
	Loader2,
	PauseCircle,
	Search,
	Settings,
	Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import ThemeToggle from "@/components/app/ThemeToggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";

const LOG_IMPORTANT = [
	"✅",
	"❌",
	"🎵",
	"Track",
	"Starting",
	"completed",
	"📦",
	"💾",
	"🔄",
	"⬇️",
	"🔓",
];

const QUALITY_PRESETS = [
	{
		id: "atmos",
		name: "Dolby Atmos",
		badge: "Spatial",
		hint: "Immersive + animated artwork",
	},
	{
		id: "hires",
		name: "Hi-Res Lossless",
		badge: "Up to 192kHz",
		hint: "Default",
	},
	{
		id: "lossless",
		name: "Lossless (ALAC)",
		badge: "CD Quality",
		hint: "Fast + light",
	},
	{
		id: "aac",
		name: "High-Quality AAC",
		badge: "256 kbps",
		hint: "Smallest files",
	},
];

type PreviewTrack = {
	num: number;
	name: string;
	artist?: string;
	album?: string;
};

type PreviewData = {
	kind?: string;
	artist?: string;
	title?: string;
	release_type?: string;
	track_count?: number;
	tracks?: PreviewTrack[];
	preselected?: number[];
};

type LogsPayload = {
	wrapper: string[];
	downloader: string[];
	wrapper_running: boolean;
	download_running: boolean;
	progress?: { label: string; percent: number; details: string };
};

type FolderEntry = {
	name: string;
	path: string;
};

const defaultProgress = { label: "", percent: 0, details: "" };

function isNearBottom(container: HTMLDivElement | null) {
	if (!container) return true;
	return (
		container.scrollHeight - container.scrollTop - container.clientHeight < 32
	);
}

function formatDownloaderLog(line: string) {
	if (line.includes("✅") || line.includes("completed successfully"))
		return "text-emerald-600 dark:text-emerald-400";
	if (
		line.includes("❌") ||
		line.toLowerCase().includes("error") ||
		line.includes("failed")
	) {
		return "text-rose-600 dark:text-rose-400";
	}
	if (line.includes("🎵") || line.toLowerCase().includes("starting"))
		return "text-sky-600 dark:text-sky-400";
	if (line.includes("📦") || line.includes("Track"))
		return "text-amber-600 dark:text-amber-400";
	if (line.includes("⬇️") || line.includes("Downloading"))
		return "text-blue-600 dark:text-blue-400";
	if (line.includes("🔓") || line.includes("Decrypting"))
		return "text-emerald-600 dark:text-emerald-400";
	if (line.includes("🔄") || line.includes("Converting"))
		return "text-violet-600 dark:text-violet-400";
	return "text-slate-700 dark:text-slate-300";
}

function formatWrapperLog(line: string) {
	if (line.includes("✅")) return "text-emerald-600 dark:text-emerald-400";
	if (line.includes("❌") || line.toLowerCase().includes("error"))
		return "text-rose-600 dark:text-rose-400";
	if (line.includes("⚠️")) return "text-amber-600 dark:text-amber-400";
	return "text-slate-700 dark:text-slate-300";
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
	const res = await fetch(url, {
		headers: { "Content-Type": "application/json" },
		...options,
	});
	return res.json();
}

export default function App() {
	const [link, setLink] = useState("");
	const [mode, setMode] = useState<"audio" | "lyrics" | "covers">("audio");
	const [wrapperRunning, setWrapperRunning] = useState(false);
	const [downloadRunning, setDownloadRunning] = useState(false);
	const [progress, setProgress] = useState(defaultProgress);
	const [verbose, setVerbose] = useState(true);
	const [downloaderLogs, setDownloaderLogs] = useState<string[]>([]);
	const [wrapperLogs, setWrapperLogs] = useState<string[]>([]);
	const [previewData, setPreviewData] = useState<PreviewData | null>(null);
	const [dialogOpen, setDialogOpen] = useState(false);
	const [trackFilter, setTrackFilter] = useState("");
	const [selectedTracks, setSelectedTracks] = useState<Set<number>>(new Set());
	const [selectedQualities, setSelectedQualities] = useState<
		Record<string, boolean>
	>({
		atmos: false,
		hires: true,
		lossless: false,
		aac: false,
	});
	const [configDraft, setConfigDraft] = useState<Record<
		string,
		unknown
	> | null>(null);
	const [qualityError, setQualityError] = useState(false);
	const [trackError, setTrackError] = useState("");
	const [searching, setSearching] = useState(false);
	const [folders, setFolders] = useState<{
		alac: string;
		atmos: string;
		aac: string;
	} | null>(null);
	const [statusMessage, setStatusMessage] = useState<string | null>(null);
	const [savingFolders, setSavingFolders] = useState(false);
	const [folderPickerOpen, setFolderPickerOpen] = useState(false);
	const [folderPickerTarget, setFolderPickerTarget] = useState<
		"alac" | "atmos" | "aac"
	>("alac");
	const [folderPickerPath, setFolderPickerPath] = useState("");
	const [folderPickerParent, setFolderPickerParent] = useState<string | null>(
		null,
	);
	const [folderEntries, setFolderEntries] = useState<FolderEntry[]>([]);
	const [folderPickerLoading, setFolderPickerLoading] = useState(false);
	const [folderPickerError, setFolderPickerError] = useState<string | null>(
		null,
	);

	const downloaderRef = useRef<HTMLDivElement | null>(null);
	const wrapperRef = useRef<HTMLDivElement | null>(null);

	const filteredDownloaderLogs = useMemo(() => {
		if (verbose) return downloaderLogs;
		return downloaderLogs.filter((line) =>
			LOG_IMPORTANT.some((key) => line.includes(key)),
		);
	}, [downloaderLogs, verbose]);

	const filteredTracks = useMemo(() => {
		const tracks = previewData?.tracks ?? [];
		if (!trackFilter.trim()) return tracks;
		const needle = trackFilter.trim().toLowerCase();
		return tracks.filter((track) => {
			const haystack =
				`${track.num} ${track.name} ${track.artist ?? ""} ${track.album ?? ""}`
					.toLowerCase()
					.trim();
			return haystack.includes(needle);
		});
	}, [previewData, trackFilter]);

	useEffect(() => {
		if (!previewData?.tracks) return;
		const preselected = new Set(previewData.preselected ?? []);
		const defaultSelectAll = preselected.size === 0;
		const nextSelected = new Set<number>();
		previewData.tracks.forEach((track) => {
			if (defaultSelectAll || preselected.has(track.num)) {
				nextSelected.add(track.num);
			}
		});
		setSelectedTracks(nextSelected);
		setTrackFilter("");
		setTrackError("");
		setQualityError(false);
		setSelectedQualities({
			atmos: false,
			hires: true,
			lossless: false,
			aac: false,
		});
	}, [previewData]);

	useEffect(() => {
		const loadFolders = async () => {
			try {
				const data = await fetchJson<{
					status: string;
					config?: Record<string, unknown>;
				}>("/api/get-config");
				if (data.status === "ok" && data.config) {
					setConfigDraft(data.config);
					setFolders({
						alac: String(data.config["alac-save-folder"] ?? "AM-DL downloads"),
						atmos: String(
							data.config["atmos-save-folder"] ?? "AM-DL-Atmos downloads",
						),
						aac: String(
							data.config["aac-save-folder"] ?? "AM-DL-AAC downloads",
						),
					});
					return;
				}
			} catch {
				// ignore
			}

			try {
				const fallback = await fetchJson<{
					status: string;
					folders: { alac: string; atmos: string; aac: string };
				}>("/api/get-download-folders");
				if (fallback.status === "ok") setFolders(fallback.folders);
			} catch {
				// ignore
			}
		};
		loadFolders();
	}, []);

	useEffect(() => {
		let mounted = true;
		const tick = async () => {
			try {
				const data = await fetchJson<LogsPayload>("/api/get-logs");
				if (!mounted) return;
				const shouldScrollDownloader = isNearBottom(downloaderRef.current);
				const shouldScrollWrapper = isNearBottom(wrapperRef.current);

				setDownloaderLogs(data.downloader ?? []);
				setWrapperLogs(data.wrapper ?? []);
				setWrapperRunning(data.wrapper_running);
				setDownloadRunning(data.download_running);
				setProgress(data.progress ?? defaultProgress);

				requestAnimationFrame(() => {
					if (shouldScrollDownloader && downloaderRef.current) {
						downloaderRef.current.scrollTop =
							downloaderRef.current.scrollHeight;
					}
					if (shouldScrollWrapper && wrapperRef.current) {
						wrapperRef.current.scrollTop = wrapperRef.current.scrollHeight;
					}
				});
			} catch {
				// ignore
			}
		};

		tick();
		const interval = setInterval(tick, 2000);
		return () => {
			mounted = false;
			clearInterval(interval);
		};
	}, []);

	useEffect(() => {
		if (!statusMessage) return;
		const timeout = setTimeout(() => setStatusMessage(null), 4000);
		return () => clearTimeout(timeout);
	}, [statusMessage]);

	const handleSearch = async () => {
		if (!link.trim()) {
			setStatusMessage("Please paste a valid Apple Music URL first.");
			return;
		}

		setSearching(true);

		try {
			const res = await fetchJson<{
				status: string;
				msg?: string;
				data?: PreviewData;
			}>("/api/preview", {
				method: "POST",
				body: JSON.stringify({ link }),
			});

			if (res.status !== "ok") {
				setStatusMessage(res.msg || "Preview failed.");
				return;
			}

			setPreviewData(res.data ?? null);
			setDialogOpen(true);
		} catch {
			setStatusMessage("Failed to load track list.");
		} finally {
			setSearching(false);
		}
	};

	const handleStartDownload = async () => {
		if (!previewData?.tracks?.length) {
			setTrackError("No tracks available to download.");
			return;
		}

		const selectedNums = Array.from(selectedTracks).sort((a, b) => a - b);
		if (selectedNums.length === 0) {
			setTrackError("Please select at least one track.");
			return;
		}

		const formats = Object.entries(selectedQualities)
			.filter(([, isSelected]) => isSelected)
			.map(([key]) => key);

		if (mode === "audio" && formats.length === 0) {
			setQualityError(true);
			return;
		}

		setQualityError(false);
		setTrackError("");

		const payload = {
			link,
			formats: mode === "audio" ? formats : ["lossless"],
			mode,
			select_tracks: selectedNums.join(","),
			artist: previewData?.artist ?? "",
			title: previewData?.title ?? "",
			release_type: previewData?.release_type ?? "Albums",
			track_count: previewData?.track_count ?? previewData?.tracks?.length ?? 1,
		};

		try {
			const res = await fetchJson<{ status: string; msg?: string }>(
				"/api/download",
				{
					method: "POST",
					body: JSON.stringify(payload),
				},
			);

			if (res.status !== "ok") {
				setStatusMessage(res.msg || "Download failed to start.");
				return;
			}

			setDialogOpen(false);
			setDownloadRunning(true);
			setStatusMessage(res.msg || "Download started.");
		} catch {
			setStatusMessage("Failed to start download.");
		}
	};

	const handleStop = async () => {
		try {
			const res = await fetchJson<{ status: string; msg?: string }>(
				"/api/stop-download",
				{
					method: "POST",
				},
			);
			setStatusMessage(res.msg || "Stop command sent.");
		} catch {
			setStatusMessage("Failed to stop download.");
		}
	};

	const toggleTrack = (trackNum: number) => {
		setSelectedTracks((prev) => {
			const next = new Set(prev);
			if (next.has(trackNum)) {
				next.delete(trackNum);
			} else {
				next.add(trackNum);
			}
			return next;
		});
	};

	const selectAllTracks = () => {
		const next = new Set<number>();
		(previewData?.tracks ?? []).forEach((track) => next.add(track.num));
		setSelectedTracks(next);
	};

	const selectNoneTracks = () => {
		setSelectedTracks(new Set());
	};

	const toggleQuality = (quality: string) => {
		setSelectedQualities((prev) => ({ ...prev, [quality]: !prev[quality] }));
	};

	const updateFolderField = (key: "alac" | "atmos" | "aac", value: string) => {
		setFolders((prev) => (prev ? { ...prev, [key]: value } : prev));
		setConfigDraft((prev) => {
			if (!prev) return prev;
			const map = {
				alac: "alac-save-folder",
				atmos: "atmos-save-folder",
				aac: "aac-save-folder",
			} as const;
			return { ...prev, [map[key]]: value };
		});
	};

	const handleSaveFolders = async () => {
		if (!configDraft) {
			setStatusMessage("Load config before saving folders.");
			return;
		}
		setSavingFolders(true);
		try {
			const res = await fetchJson<{ status: string; msg?: string }>(
				"/api/save-config",
				{
					method: "POST",
					body: JSON.stringify(configDraft),
				},
			);
			if (res.status === "ok") {
				setStatusMessage(res.msg || "Download destinations updated.");
			} else {
				setStatusMessage(res.msg || "Failed to save download destinations.");
			}
		} catch {
			setStatusMessage("Failed to save download destinations.");
		} finally {
			setSavingFolders(false);
		}
	};

	const loadFolderEntries = async (pathValue?: string) => {
		setFolderPickerLoading(true);
		setFolderPickerError(null);
		try {
			const query = pathValue ? `?path=${encodeURIComponent(pathValue)}` : "";
			const res = await fetchJson<{
				status: string;
				path?: string;
				parent?: string | null;
				entries?: FolderEntry[];
				msg?: string;
			}>(`/api/fs${query}`);
			if (res.status === "ok" && res.path && res.entries) {
				setFolderPickerPath(res.path);
				setFolderPickerParent(res.parent === undefined ? null : res.parent);
				setFolderEntries(res.entries);
				setFolderPickerError(null);
			} else {
				setFolderPickerError(res.msg || "Failed to load folders.");
			}
		} catch {
			setFolderPickerError("Failed to load folders.");
		} finally {
			setFolderPickerLoading(false);
		}
	};

	const openFolderPicker = (target: "alac" | "atmos" | "aac") => {
		setFolderPickerTarget(target);
		setFolderPickerOpen(true);
		const startPath = folders?.[target] || "";
		loadFolderEntries(startPath);
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-amber-50 via-white to-rose-50 text-slate-900 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 dark:text-slate-100">
			<div className="relative overflow-hidden">
				<div className="pointer-events-none absolute inset-0 opacity-60">
					<div className="absolute -left-32 top-0 h-72 w-72 rounded-full bg-sky-200/40 blur-3xl dark:bg-indigo-500/10" />
					<div className="absolute right-0 top-20 h-72 w-72 rounded-full bg-orange-200/50 blur-3xl dark:bg-amber-500/10" />
				</div>

				<div className="relative mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 pb-16 pt-10">
					<header className="flex flex-col gap-4">
						<div className="flex flex-wrap items-center justify-between gap-4">
							<div>
								<p className="text-sm uppercase tracking-[0.3em] text-slate-400 dark:text-slate-500">
									Apple Music Rip
								</p>
								<h1 className="text-3xl font-semibold text-slate-900 dark:text-slate-100 sm:text-4xl">
									Build pristine libraries faster.
								</h1>
								<p className="mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
									A modern control room for Apple Music downloads. Preview, pick
									tracks, and monitor every conversion step in one place.
								</p>
							</div>
							<div className="flex items-center gap-3">
								<Badge
									variant="secondary"
									className={
										wrapperRunning
											? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-300"
											: "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-300"
									}
								>
									{wrapperRunning ? "Wrapper Connected" : "Wrapper Offline"}
								</Badge>
								<ThemeToggle />
								<Button variant="outline" className="gap-2" asChild>
									<a href="/settings">
										<Settings className="h-4 w-4" />
										Settings
									</a>
								</Button>
							</div>
						</div>

						{statusMessage ? (
							<div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
								{statusMessage}
							</div>
						) : null}
					</header>

					<section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
						<div className="flex flex-col gap-6">
							<Card className="border-slate-200/60 shadow-sm dark:border-slate-800/80 dark:bg-slate-950/40">
								<CardHeader>
									<CardTitle className="flex items-center gap-2 text-lg">
										<Sparkles className="h-5 w-5 text-amber-500 dark:text-amber-300" />
										New download
									</CardTitle>
									<CardDescription>
										Paste a link, choose a mode, and we will grab the track
										list.
									</CardDescription>
								</CardHeader>
								<CardContent className="flex flex-col gap-4">
									<div className="grid gap-2">
										<Label htmlFor="link">Apple Music URL</Label>
										<Input
											id="link"
											placeholder="https://music.apple.com/..."
											value={link}
											onChange={(event) => setLink(event.target.value)}
										/>
									</div>

									<div className="grid gap-3 rounded-xl border border-slate-200 bg-white/70 p-4 dark:border-slate-800 dark:bg-slate-900/70">
										<div className="flex w-full items-center justify-between gap-3">
											<div>
												<p className="text-sm font-medium text-slate-900 dark:text-slate-100">
													Download mode
												</p>
												<p className="text-xs text-slate-500 dark:text-slate-400">
													Lyrics & covers still use a track list for targeting.
												</p>
											</div>
											<Badge
												variant="outline"
												className="border-slate-200 text-slate-600 dark:border-slate-700 dark:text-slate-300"
											>
												{mode.toUpperCase()}
											</Badge>
										</div>
										<RadioGroup
											value={mode}
											onValueChange={(value) => setMode(value as typeof mode)}
										>
											<div className="grid gap-3 sm:grid-cols-3">
												{[
													{ id: "audio", title: "Audio" },
													{ id: "lyrics", title: "Lyrics Only" },
													{ id: "covers", title: "Covers Only" },
												].map((item) => (
													<label
														key={item.id}
														htmlFor={`mode-${item.id}`}
														className="flex cursor-pointer items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-950"
													>
														<RadioGroupItem
															id={`mode-${item.id}`}
															value={item.id}
														/>
														<span className="font-medium text-slate-700 dark:text-slate-200">
															{item.title}
														</span>
													</label>
												))}
											</div>
										</RadioGroup>
									</div>

									<div className="flex flex-wrap gap-3">
										<Button
											className="gap-2"
											onClick={handleSearch}
											disabled={!wrapperRunning || searching || downloadRunning}
										>
											{searching ? (
												<Loader2 className="h-4 w-4 animate-spin" />
											) : (
												<Search className="h-4 w-4" />
											)}
											{searching ? "Loading tracks" : "Search"}
										</Button>
										{downloadRunning ? (
											<Button
												variant="destructive"
												className="gap-2"
												onClick={handleStop}
											>
												<PauseCircle className="h-4 w-4" />
												Stop
											</Button>
										) : null}
									</div>
								</CardContent>
							</Card>

							{folders ? (
								<Card className="border-slate-200/60 bg-white/80 dark:border-slate-800/80 dark:bg-slate-950/50">
									<CardHeader>
										<CardTitle className="flex items-center gap-2 text-base">
											<FolderOpen className="h-4 w-4 text-slate-500 dark:text-slate-400" />
											Download destinations
										</CardTitle>
										<CardDescription>
											Keep track of where each format lands.
										</CardDescription>
									</CardHeader>
									<CardContent className="grid gap-4">
										<div className="grid gap-3 sm:grid-cols-3">
											<div className="grid gap-2">
												<Label className="text-xs uppercase tracking-widest text-slate-400 dark:text-slate-500">
													ALAC
												</Label>
												<div className="flex gap-2">
													<Input
														className="flex-1"
														value={folders.alac}
														onChange={(event) =>
															updateFolderField("alac", event.target.value)
														}
													/>
													<Button
														variant="outline"
														size="sm"
														onClick={() => openFolderPicker("alac")}
													>
														Browse
													</Button>
												</div>
											</div>
											<div className="grid gap-2">
												<Label className="text-xs uppercase tracking-widest text-slate-400 dark:text-slate-500">
													Atmos
												</Label>
												<div className="flex gap-2">
													<Input
														className="flex-1"
														value={folders.atmos}
														onChange={(event) =>
															updateFolderField("atmos", event.target.value)
														}
													/>
													<Button
														variant="outline"
														size="sm"
														onClick={() => openFolderPicker("atmos")}
													>
														Browse
													</Button>
												</div>
											</div>
											<div className="grid gap-2">
												<Label className="text-xs uppercase tracking-widest text-slate-400 dark:text-slate-500">
													AAC
												</Label>
												<div className="flex gap-2">
													<Input
														className="flex-1"
														value={folders.aac}
														onChange={(event) =>
															updateFolderField("aac", event.target.value)
														}
													/>
													<Button
														variant="outline"
														size="sm"
														onClick={() => openFolderPicker("aac")}
													>
														Browse
													</Button>
												</div>
											</div>
										</div>
										<div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
											<span>Saved to config.yaml</span>
											<Button
												size="sm"
												onClick={handleSaveFolders}
												disabled={savingFolders || !configDraft}
											>
												{savingFolders ? "Saving..." : "Save destinations"}
											</Button>
										</div>
									</CardContent>
								</Card>
							) : null}

							<Card className="border-slate-200/60 dark:border-slate-800/80 dark:bg-slate-950/40">
								<CardHeader className="flex flex-col gap-3">
									<div className="flex w-full items-center justify-between gap-3">
										<CardTitle className="text-base">
											Downloader Activity
										</CardTitle>
										<div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
											<span>Verbose</span>
											<Switch checked={verbose} onCheckedChange={setVerbose} />
										</div>
									</div>
									<div className="rounded-xl border border-slate-200 bg-white/70 px-4 py-3 dark:border-slate-800 dark:bg-slate-900/70">
										<div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
											<span>{progress.label || "Waiting for a download"}</span>
											<span>{progress.percent.toFixed(0)}%</span>
										</div>
										<div className="mt-2 h-2 w-full rounded-full bg-slate-100 dark:bg-slate-800/70">
											<div
												className="h-2 rounded-full bg-gradient-to-r from-amber-400 via-orange-400 to-rose-400 transition-all"
												style={{
													width: `${Math.min(100, Math.max(0, progress.percent))}%`,
												}}
											/>
										</div>
										{progress.details ? (
											<p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
												{progress.details}
											</p>
										) : null}
									</div>
								</CardHeader>
								<CardContent>
									<div
										ref={downloaderRef}
										className="h-64 overflow-y-auto rounded-xl border border-slate-200 bg-white/70 px-4 py-3 text-xs dark:border-slate-800 dark:bg-slate-950/60"
										style={{ fontFamily: "var(--font-mono)" }}
									>
										{filteredDownloaderLogs.length === 0 ? (
											<div className="text-slate-400 dark:text-slate-500">
												No logs yet.
											</div>
										) : (
											filteredDownloaderLogs.map((line, index) => (
												<div
													key={`${line}-${index}`}
													className={`py-1 ${formatDownloaderLog(line)}`}
												>
													&gt; {line}
												</div>
											))
										)}
									</div>
								</CardContent>
							</Card>
						</div>

						<div className="flex flex-col gap-6">
							<Card className="border-slate-200/60 dark:border-slate-800/80 dark:bg-slate-950/40">
								<CardHeader>
									<CardTitle className="text-base">Wrapper Signals</CardTitle>
									<CardDescription>
										Keep an eye on the runtime container.
									</CardDescription>
								</CardHeader>
								<CardContent>
									<div
										ref={wrapperRef}
										className="h-64 overflow-y-auto rounded-xl border border-slate-200 bg-white/70 px-4 py-3 text-xs dark:border-slate-800 dark:bg-slate-950/60"
										style={{ fontFamily: "var(--font-mono)" }}
									>
										{wrapperLogs.length === 0 ? (
											<div className="text-slate-400 dark:text-slate-500">
												No wrapper logs yet.
											</div>
										) : (
											wrapperLogs.map((line, index) => (
												<div
													key={`${line}-${index}`}
													className={`py-1 ${formatWrapperLog(line)}`}
												>
													&gt; {line}
												</div>
											))
										)}
									</div>
								</CardContent>
							</Card>

							<Card className="border-slate-200/60 bg-slate-950 text-slate-100 dark:border-slate-800/80 dark:bg-slate-900">
								<CardHeader>
									<CardTitle className="flex items-center gap-2 text-base">
										<Info className="h-4 w-4 text-amber-300 dark:text-amber-200" />
										Quick tips
									</CardTitle>
								</CardHeader>
								<CardContent className="space-y-3 text-sm text-slate-200">
									<div className="flex gap-3">
										<div className="mt-1 h-2 w-2 rounded-full bg-amber-300" />
										<p>
											Run the wrapper container and sign in before starting
											downloads.
										</p>
									</div>
									<div className="flex gap-3">
										<div className="mt-1 h-2 w-2 rounded-full bg-amber-300" />
										<p>
											Hi-Res is the default quality. Toggle more formats in the
											selection modal.
										</p>
									</div>
									<div className="flex gap-3">
										<div className="mt-1 h-2 w-2 rounded-full bg-amber-300" />
										<p>
											Save paths can be customized in Settings without stopping
											the UI.
										</p>
									</div>
								</CardContent>
							</Card>
						</div>
					</section>
				</div>
			</div>

			<Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
				<DialogContent className="max-w-4xl dark:border-slate-800 dark:bg-slate-950/95">
					<DialogHeader>
						<DialogTitle className="text-xl">Select tracks</DialogTitle>
						<DialogDescription>
							{previewData?.artist || ""}
							{previewData?.artist && previewData?.title ? " — " : ""}
							{previewData?.title || ""}
						</DialogDescription>
					</DialogHeader>

					<div className="grid gap-6">
						<div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900/60">
							<div className="flex items-start justify-between gap-4">
								<div>
									<p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
										Audio qualities
									</p>
									<p className="text-xs text-slate-500 dark:text-slate-400">
										Non-Atmos formats will be converted to FLAC automatically.
									</p>
								</div>
								<Badge
									variant="secondary"
									className="border-slate-200 dark:border-slate-700 dark:text-slate-200"
								>
									{mode === "audio" ? "Audio mode" : "Lyrics/Covers mode"}
								</Badge>
							</div>

							<div className="mt-4 grid gap-3 sm:grid-cols-2">
								{QUALITY_PRESETS.map((quality) => (
									<label
										key={quality.id}
										className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition ${
											selectedQualities[quality.id]
												? "border-amber-300 bg-amber-50 dark:border-amber-500/50 dark:bg-amber-500/10"
												: "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950"
										} ${mode !== "audio" ? "opacity-50" : ""}`}
									>
										<Checkbox
											checked={selectedQualities[quality.id]}
											onCheckedChange={() =>
												mode === "audio" && toggleQuality(quality.id)
											}
										/>
										<div>
											<div className="flex items-center gap-2">
												<p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
													{quality.name}
												</p>
												<Badge
													variant="outline"
													className="border-slate-200 text-[10px] dark:border-slate-700 dark:text-slate-300"
												>
													{quality.badge}
												</Badge>
											</div>
											<p className="text-xs text-slate-500 dark:text-slate-400">
												{quality.hint}
											</p>
										</div>
									</label>
								))}
							</div>

							{qualityError ? (
								<p className="mt-3 text-xs text-rose-500 dark:text-rose-400">
									Select at least one quality.
								</p>
							) : null}
						</div>

						<div className="grid gap-4">
							<div className="flex flex-wrap items-center justify-between gap-3">
								<div className="flex items-center gap-2">
									<Input
										placeholder="Search tracks"
										value={trackFilter}
										onChange={(event) => setTrackFilter(event.target.value)}
										className="w-64"
									/>
									<Badge
										variant="outline"
										className="border-slate-200 dark:border-slate-700 dark:text-slate-300"
									>
										{filteredTracks.length} shown
									</Badge>
								</div>
								<div className="flex gap-2">
									<Button variant="outline" size="sm" onClick={selectAllTracks}>
										Select all
									</Button>
									<Button
										variant="outline"
										size="sm"
										onClick={selectNoneTracks}
									>
										Select none
									</Button>
								</div>
							</div>

							<Separator />

							<div
								className="max-h-[38vh] overflow-y-auto rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm dark:border-slate-800 dark:bg-slate-950"
								style={{ fontFamily: "var(--font-mono)" }}
							>
								{filteredTracks.length === 0 ? (
									<p className="text-slate-400 dark:text-slate-500">
										No tracks match that search.
									</p>
								) : (
									filteredTracks.map((track) => (
										<label
											key={track.num}
											className="flex cursor-pointer items-start gap-3 border-b border-slate-100 py-3 last:border-b-0 dark:border-slate-800/70"
										>
											<Checkbox
												checked={selectedTracks.has(track.num)}
												onCheckedChange={() => toggleTrack(track.num)}
											/>
											<div>
												<p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
													{String(track.num).padStart(2, "0")} — {track.name}
												</p>
												<p className="text-xs text-slate-500 dark:text-slate-400">
													{track.artist ??
														previewData?.artist ??
														"Unknown Artist"}{" "}
													· {track.album ?? previewData?.title}
												</p>
											</div>
										</label>
									))
								)}
							</div>

							<div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
								<span>{selectedTracks.size} selected</span>
								<span>{previewData?.kind ? `${previewData.kind}` : ""}</span>
							</div>

							{trackError ? (
								<p className="text-xs text-rose-500 dark:text-rose-400">
									{trackError}
								</p>
							) : null}

							<div className="flex items-center justify-end gap-3">
								<Button variant="outline" onClick={() => setDialogOpen(false)}>
									Cancel
								</Button>
								<Button className="gap-2" onClick={handleStartDownload}>
									<Download className="h-4 w-4" />
									Start download
								</Button>
							</div>
						</div>
					</div>
				</DialogContent>
			</Dialog>

			<Dialog open={folderPickerOpen} onOpenChange={setFolderPickerOpen}>
				<DialogContent className="max-w-2xl dark:border-slate-800 dark:bg-slate-950/95">
					<DialogHeader>
						<DialogTitle className="text-lg">Choose folder</DialogTitle>
						<DialogDescription>
							Select a destination for{" "}
							<span className="font-semibold uppercase">
								{folderPickerTarget}
							</span>
							.
						</DialogDescription>
					</DialogHeader>

					<div className="grid gap-3">
						<div className="flex flex-wrap items-center gap-2">
							<Button
								variant="outline"
								size="sm"
								disabled={!folderPickerParent || folderPickerLoading}
								onClick={() =>
									folderPickerParent && loadFolderEntries(folderPickerParent)
								}
							>
								Up
							</Button>
							<Input
								className="flex-1"
								value={folderPickerPath}
								onChange={(event) => setFolderPickerPath(event.target.value)}
								onKeyDown={(event) => {
									if (event.key === "Enter") {
										loadFolderEntries(folderPickerPath);
									}
								}}
							/>
							<Button
								variant="outline"
								size="sm"
								disabled={folderPickerLoading}
								onClick={() => loadFolderEntries(folderPickerPath)}
							>
								Go
							</Button>
						</div>

						{folderPickerError ? (
							<p className="text-xs text-rose-500 dark:text-rose-400">
								{folderPickerError}
							</p>
						) : null}

						<div className="max-h-64 overflow-y-auto rounded-xl border border-slate-200 bg-white/70 px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-950/60">
							{folderPickerLoading ? (
								<p className="text-xs text-slate-500 dark:text-slate-400">
									Loading folders...
								</p>
							) : folderEntries.length === 0 ? (
								<p className="text-xs text-slate-500 dark:text-slate-400">
									No folders found.
								</p>
							) : (
								folderEntries.map((entry) => (
									<button
										key={entry.path}
										type="button"
										onClick={() => loadFolderEntries(entry.path)}
										className="flex w-full items-center justify-between rounded-lg px-2 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-900/70"
									>
										<span>{entry.name}</span>
									</button>
								))
							)}
						</div>

						<div className="flex items-center justify-end gap-3">
							<Button
								variant="outline"
								onClick={() => setFolderPickerOpen(false)}
							>
								Cancel
							</Button>
							<Button
								onClick={() => {
									updateFolderField(folderPickerTarget, folderPickerPath);
									setFolderPickerOpen(false);
								}}
							>
								Select this folder
							</Button>
						</div>
					</div>
				</DialogContent>
			</Dialog>
		</div>
	);
}
