import { ChevronLeft, Loader2, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import ThemeToggle from "@/components/app/ThemeToggle";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
	createEmptyMetadataCustomTagRule,
	DEFAULT_METADATA_TAGS_BY_CONTAINER,
	isMetadataCustomTagRuleValid,
	METADATA_CONTAINER_SHORT_LABELS,
	METADATA_CONTAINERS,
	METADATA_CUSTOM_TAG_RULES_KEY,
	METADATA_SOURCE_FORMAT_LABELS,
	METADATA_SOURCE_FORMATS,
	METADATA_TAG_OPTIONS_BY_CONTAINER,
	type MetadataContainer,
	type MetadataCustomTagRule,
	type MetadataSourceFormat,
	normalizeMetadataCustomTagRule,
	resolveMetadataCustomTagRulesFromConfig,
	serializeMetadataCustomTagRulesForConfig,
	validateMetadataCustomTagRule,
} from "./metadataProfiles";

type FieldType =
	| "text"
	| "number"
	| "textarea"
	| "string-list"
	| "select"
	| "multi-select"
	| "switch";

type Field = {
	id: string;
	label: string;
	type: FieldType;
	placeholder?: string;
	helper?: string;
	options?: ReadonlyArray<{ value: string; label: string }>;
	defaultValues?: string[];
};

type Section = {
	id: string;
	title: string;
	description: string;
	badge?: string;
	fields: Field[];
};

const SECTIONS: Section[] = [
	{
		id: "access",
		title: "Access & Region",
		description:
			"Tokens and storefront configuration for Apple Music services.",
		badge: "Required",
		fields: [
			{
				id: "media-user-token",
				label: "Media User Token",
				type: "text",
				placeholder: "your-media-user-token",
				helper: "Required for lyrics and AAC-LC downloads.",
			},
			{
				id: "authorization-token",
				label: "Authorization Token",
				type: "text",
				placeholder: "your-authorization-token",
				helper: "Usually auto-obtained. Only change if needed.",
			},
			{
				id: "language",
				label: "Language",
				type: "text",
				placeholder: "en-US",
			},
			{
				id: "storefront",
				label: "Storefront",
				type: "text",
				placeholder: "us, jp, ca",
				helper:
					"Use the 2-letter country code that matches your account region.",
			},
		],
	},
	{
		id: "downloads",
		title: "Downloads",
		description: "Audio formats, output folders, and general limits.",
		fields: [
			{
				id: "alac-save-folder",
				label: "ALAC Folder",
				type: "text",
				placeholder: "AM-DL downloads",
			},
			{
				id: "atmos-save-folder",
				label: "Atmos Folder",
				type: "text",
				placeholder: "AM-DL-Atmos downloads",
			},
			{
				id: "aac-save-folder",
				label: "AAC Folder",
				type: "text",
				placeholder: "AM-DL-AAC downloads",
			},
			{
				id: "aac-type",
				label: "AAC Type",
				type: "select",
				options: [
					{ value: "aac-lc", label: "AAC-LC" },
					{ value: "aac", label: "AAC" },
					{ value: "aac-binaural", label: "AAC Binaural" },
					{ value: "aac-downmix", label: "AAC Downmix" },
				],
			},
			{
				id: "alac-max",
				label: "ALAC Max Quality",
				type: "select",
				options: [
					{ value: "192000", label: "192 kHz" },
					{ value: "96000", label: "96 kHz" },
					{ value: "48000", label: "48 kHz" },
					{ value: "44100", label: "44.1 kHz" },
				],
			},
			{
				id: "atmos-max",
				label: "Atmos Max Quality",
				type: "select",
				options: [
					{ value: "2768", label: "2768 kbps" },
					{ value: "2448", label: "2448 kbps" },
				],
			},
			{
				id: "limit-max",
				label: "Download Limit",
				type: "number",
				placeholder: "200",
			},
		],
	},
	{
		id: "artwork",
		title: "Artwork & Lyrics",
		description: "Cover sizes, formats, and lyric preferences.",
		fields: [
			{
				id: "cover-size",
				label: "Cover Size",
				type: "text",
				placeholder: "5000x5000",
			},
			{
				id: "cover-format",
				label: "Cover Format",
				type: "select",
				options: [
					{ value: "jpg", label: "JPG" },
					{ value: "png", label: "PNG" },
					{ value: "original", label: "Original" },
				],
			},
			{
				id: "embed-cover",
				label: "Embed Cover Art",
				type: "switch",
			},
			{
				id: "save-cover-file",
				label: "Save Cover File",
				type: "switch",
				helper:
					"Writes album/playlist cover images to disk. Embedding may still create a cover file.",
			},
			{
				id: "save-artist-cover",
				label: "Save Artist Cover",
				type: "switch",
				helper: "Uses the cover size/format above.",
			},
			{
				id: "save-animated-artwork",
				label: "Save Animated Artwork",
				type: "switch",
			},
			{
				id: "emby-animated-artwork",
				label: "Emby Animated Artwork",
				type: "switch",
			},
			{
				id: "lrc-type",
				label: "Lyrics Type",
				type: "select",
				options: [
					{ value: "lyrics", label: "Lyrics" },
					{ value: "syllable-lyrics", label: "Syllable Lyrics" },
				],
			},
			{
				id: "lrc-format",
				label: "Lyrics Format",
				type: "select",
				options: [
					{ value: "lrc", label: "LRC" },
					{ value: "ttml", label: "TTML" },
				],
			},
			{
				id: "embed-lrc",
				label: "Embed Lyrics",
				type: "switch",
			},
			{
				id: "save-lrc-file",
				label: "Save Lyrics File",
				type: "switch",
			},
		],
	},
	{
		id: "naming",
		title: "Naming & Tags",
		description: "Folder formats, naming templates, and tag behavior.",
		fields: [
			{
				id: "album-folder-format",
				label: "Album Folder Format",
				type: "textarea",
				placeholder: "{AlbumName}",
				helper:
					"Variables: {AlbumId}, {AlbumName}, {ArtistName}, {ReleaseDate}, {ReleaseYear}, {UPC}, {Copyright}, {Quality}, {Codec}, {Tag}, {RecordLabel}",
			},
			{
				id: "playlist-folder-format",
				label: "Playlist Folder Format",
				type: "textarea",
				placeholder: "{PlaylistName}",
				helper:
					"Variables: {PlaylistId}, {PlaylistName}, {ArtistName}, {Quality}, {Codec}, {Tag}",
			},
			{
				id: "song-file-format",
				label: "Song File Format",
				type: "textarea",
				placeholder: "{SongNumer}. {SongName}",
				helper:
					"Variables: {SongId}, {SongNumer}, {SongName}, {DiscNumber}, {TrackNumber}, {Quality}, {Codec}, {Tag}",
			},
			{
				id: "artist-folder-format",
				label: "Artist Folder Format",
				type: "textarea",
				placeholder: "{UrlArtistName}",
				helper: "Leave empty to disable artist folders.",
			},
			{
				id: "explicit-choice",
				label: "Explicit Tag",
				type: "text",
				placeholder: "[E]",
			},
			{
				id: "clean-choice",
				label: "Clean Tag",
				type: "text",
				placeholder: "[C]",
			},
			{
				id: "apple-master-choice",
				label: "Apple Master Tag",
				type: "text",
				placeholder: "[M]",
			},
			{
				id: "use-songinfo-for-playlist",
				label: "Use Song Info for Playlist",
				type: "switch",
			},
			{
				id: "dl-albumcover-for-playlist",
				label: "Download Album Cover for Playlist",
				type: "switch",
			},
		],
	},
	{
		id: "conversion",
		title: "Conversion",
		description: "Post-download conversion and ffmpeg controls.",
		fields: [
			{
				id: "convert-after-download",
				label: "Convert After Download",
				type: "switch",
				helper: "Requires ffmpeg.",
			},
			{
				id: "alac-repair-mode",
				label: "ALAC Repair Mode",
				type: "select",
				options: [
					{ value: "all", label: "Repair All ALAC" },
					{ value: "corrupt-only", label: "Repair Corrupt Only" },
					{ value: "off", label: "Off" },
				],
				helper:
					"Uses macOS alac_at when available; Windows/Linux will fall back to ffmpeg's native decoder.",
			},
			{
				id: "convert-format",
				label: "Convert Format",
				type: "select",
				options: [
					{ value: "flac", label: "FLAC" },
					{ value: "mp3", label: "MP3" },
					{ value: "opus", label: "Opus" },
					{ value: "wav", label: "WAV" },
					{ value: "copy", label: "Copy (no re-encode)" },
				],
			},
			// Custom: choose which source formats should be converted.
			{
				id: "convert-formats",
				label: "Convert Formats",
				type: "multi-select",
				options: [
					{ value: "lossless", label: "Lossless (ALAC)" },
					{ value: "hires", label: "Hi-Res Lossless" },
					{ value: "aac", label: "AAC" },
					{ value: "atmos", label: "Dolby Atmos" },
				],
				helper:
					"Choose which source formats get converted. Defaults to lossless, hi-res, AAC when unset.",
				defaultValues: ["lossless", "hires", "aac"],
			},
			{
				id: "convert-keep-original",
				label: "Keep Original",
				type: "switch",
			},
			{
				id: "convert-warn-lossy-to-lossless",
				label: "Warn on Lossy to Lossless",
				type: "switch",
				helper: "Show a warning when converting lossy sources to lossless.",
			},
			{
				id: "convert-skip-lossy-to-lossless",
				label: "Skip Lossy to Lossless",
				type: "switch",
				helper: "Skip converting lossy sources to lossless outputs.",
			},
			{
				id: "convert-skip-if-source-matches",
				label: "Skip if Source Matches",
				type: "switch",
			},
			{
				id: "ffmpeg-path",
				label: "FFmpeg Path",
				type: "text",
				placeholder: "ffmpeg",
			},
			{
				id: "convert-extra-args",
				label: "Extra FFmpeg Arguments",
				type: "text",
				placeholder: "Additional ffmpeg arguments",
			},
		],
	},
	{
		id: "metadata",
		title: "Metadata",
		description:
			"Configure tag profiles by target container and advanced custom tags.",
		fields: [
			{
				id: "metadata-tags-m4a",
				label: "M4A / MP4 Tags",
				type: "multi-select",
				options: METADATA_TAG_OPTIONS_BY_CONTAINER.m4a,
				defaultValues: DEFAULT_METADATA_TAGS_BY_CONTAINER.m4a,
				helper:
					"Default metadata profile for M4A/MP4 outputs (ALAC, AAC, Atmos). When unset, all known tags are enabled.",
			},
			{
				id: "metadata-tags-flac",
				label: "FLAC Tags",
				type: "multi-select",
				options: METADATA_TAG_OPTIONS_BY_CONTAINER.flac,
				defaultValues: DEFAULT_METADATA_TAGS_BY_CONTAINER.flac,
				helper:
					"Default metadata profile for FLAC outputs. Apple-specific iTunes IDs are omitted for FLAC.",
			},
			{
				id: "metadata-atmos-prefix",
				label: "Atmos Prefix (🄳)",
				type: "switch",
				helper:
					"Prefix Atmos track Title and Album tags with 🄳 for easier identification in players.",
			},
		],
	},
	{
		id: "advanced",
		title: "Advanced",
		description: "Ports, memory limits, and technical overrides.",
		fields: [
			{
				id: "max-memory-limit",
				label: "Max Memory Limit (MB)",
				type: "number",
				placeholder: "256",
			},
			{
				id: "decrypt-m3u8-port",
				label: "Decrypt M3U8 Port",
				type: "text",
				placeholder: "127.0.0.1:10020",
			},
			{
				id: "get-m3u8-port",
				label: "Get M3U8 Port",
				type: "text",
				placeholder: "127.0.0.1:20020",
			},
			{
				id: "get-m3u8-mode",
				label: "M3U8 Mode",
				type: "select",
				options: [
					{ value: "web", label: "Web Only" },
					{ value: "hires", label: "Hi-Res Only" },
					{ value: "all", label: "All" },
				],
			},
			{
				id: "mv-audio-type",
				label: "MV Audio Type",
				type: "select",
				options: [
					{ value: "atmos", label: "Atmos" },
					{ value: "ac3", label: "AC3" },
					{ value: "aac", label: "AAC" },
				],
			},
			{
				id: "mv-max",
				label: "MV Max Quality",
				type: "number",
				placeholder: "2160",
			},
			{
				id: "get-m3u8-from-device",
				label: "Get M3U8 from Device",
				type: "switch",
			},
		],
	},
];

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
	const res = await fetch(url, {
		headers: { "Content-Type": "application/json" },
		...options,
	});
	return res.json();
}

export default function SettingsApp() {
	const [config, setConfig] = useState<Record<string, unknown>>({});
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [message, setMessage] = useState<{
		type: "success" | "error";
		text: string;
	} | null>(null);

	const sectionIds = useMemo(() => SECTIONS.map((section) => section.id), []);

	useEffect(() => {
		const loadConfig = async () => {
			try {
				const data = await fetchJson<{
					status: string;
					config?: Record<string, unknown>;
					msg?: string;
				}>("/api/get-config");
				if (data.status === "ok" && data.config) {
					setConfig({
						...data.config,
						"metadata-atmos-prefix":
							data.config["metadata-atmos-prefix"] ?? true,
					});
				} else {
					setMessage({
						type: "error",
						text: data.msg || "Failed to load configuration.",
					});
				}
			} catch {
				setMessage({ type: "error", text: "Failed to load configuration." });
			} finally {
				setLoading(false);
			}
		};

		loadConfig();
	}, []);

	useEffect(() => {
		if (!message) return;
		const timeout = setTimeout(() => setMessage(null), 5000);
		return () => clearTimeout(timeout);
	}, [message]);

	const updateValue = (id: string, value: unknown) => {
		setConfig((prev) => ({ ...prev, [id]: value }));
	};

	const metadataCustomTagRules = useMemo(
		() => resolveMetadataCustomTagRulesFromConfig(config),
		[config],
	);
	const metadataCustomTagRuleValidations = useMemo(
		() =>
			metadataCustomTagRules.map((rule) => validateMetadataCustomTagRule(rule)),
		[metadataCustomTagRules],
	);
	const hasInvalidMetadataCustomTagRules = useMemo(
		() =>
			metadataCustomTagRuleValidations.some(
				(validation) => !isMetadataCustomTagRuleValid(validation),
			),
		[metadataCustomTagRuleValidations],
	);

	const persistMetadataCustomTagRules = (rules: MetadataCustomTagRule[]) => {
		updateValue(
			METADATA_CUSTOM_TAG_RULES_KEY,
			serializeMetadataCustomTagRulesForConfig(rules),
		);
	};

	const updateMetadataCustomTagRule = (
		index: number,
		patch: Partial<MetadataCustomTagRule>,
	) => {
		const nextRules = metadataCustomTagRules.map((rule, currentIndex) =>
			currentIndex === index
				? normalizeMetadataCustomTagRule({ ...rule, ...patch })
				: normalizeMetadataCustomTagRule(rule),
		);
		persistMetadataCustomTagRules(nextRules);
	};

	const toggleMetadataCustomRuleContainer = (
		index: number,
		container: MetadataContainer,
	) => {
		const row = metadataCustomTagRules[index];
		if (!row) return;
		const nextSet = new Set(row.containers);
		if (nextSet.has(container)) {
			nextSet.delete(container);
		} else {
			nextSet.add(container);
		}
		updateMetadataCustomTagRule(index, {
			containers: METADATA_CONTAINERS.filter((value) => nextSet.has(value)),
		});
	};

	const toggleMetadataCustomRuleSourceFormat = (
		index: number,
		sourceFormat: MetadataSourceFormat,
	) => {
		const row = metadataCustomTagRules[index];
		if (!row) return;
		const nextSet = new Set(row.sourceFormats);
		if (nextSet.has(sourceFormat)) {
			nextSet.delete(sourceFormat);
		} else {
			nextSet.add(sourceFormat);
		}
		updateMetadataCustomTagRule(index, {
			sourceFormats: METADATA_SOURCE_FORMATS.filter((value) =>
				nextSet.has(value),
			),
		});
	};

	const addMetadataCustomTagRule = () => {
		persistMetadataCustomTagRules([
			...metadataCustomTagRules,
			createEmptyMetadataCustomTagRule(),
		]);
	};

	const addAtmosAlbumVersionPreset = () => {
		persistMetadataCustomTagRules([
			...metadataCustomTagRules,
			normalizeMetadataCustomTagRule({
				key: "ALBUMVERSION",
				value: "Dolby Atmos",
				containers: ["m4a"],
				"source-formats": ["atmos"],
			}),
		]);
	};

	const removeMetadataCustomTagRule = (index: number) => {
		persistMetadataCustomTagRules(
			metadataCustomTagRules.filter(
				(_, currentIndex) => currentIndex !== index,
			),
		);
	};

	const handleSave = async () => {
		if (hasInvalidMetadataCustomTagRules) {
			setMessage({
				type: "error",
				text: "Fix invalid custom metadata tag rules before saving.",
			});
			return;
		}

		const nextConfig = {
			...config,
			[METADATA_CUSTOM_TAG_RULES_KEY]: serializeMetadataCustomTagRulesForConfig(
				metadataCustomTagRules,
			),
		};
		delete nextConfig["metadata-custom-tags-m4a"];
		delete nextConfig["metadata-custom-tags-flac"];

		setSaving(true);
		try {
			const res = await fetchJson<{ status: string; msg?: string }>(
				"/api/save-config",
				{
					method: "POST",
					body: JSON.stringify(nextConfig),
				},
			);
			if (res.status === "ok") {
				setConfig(nextConfig);
				setMessage({ type: "success", text: res.msg || "Settings saved." });
			} else {
				setMessage({ type: "error", text: res.msg || "Save failed." });
			}
		} catch {
			setMessage({ type: "error", text: "Save failed." });
		} finally {
			setSaving(false);
		}
	};

	const renderField = (field: Field) => {
		const value = config[field.id];
		const useMono =
			field.type === "string-list" ||
			field.id.includes("folder") ||
			field.id.includes("path") ||
			field.id.includes("format");
		const inputClassName = useMono ? "font-mono text-xs" : "";

		if (field.type === "switch") {
			return (
				<div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-800 dark:bg-slate-950">
					<div>
						<p className="text-sm font-medium text-slate-800 dark:text-slate-100">
							{field.label}
						</p>
						{field.helper ? (
							<p className="text-xs text-slate-500 dark:text-slate-400">
								{field.helper}
							</p>
						) : null}
					</div>
					<Switch
						checked={Boolean(value)}
						onCheckedChange={(checked) => updateValue(field.id, checked)}
					/>
				</div>
			);
		}

		// Custom: multi-select UI for array-backed settings.
		if (field.type === "multi-select") {
			const hasValue = Object.hasOwn(config, field.id);
			const selectedValues = Array.isArray(value)
				? value.map((entry) => String(entry))
				: !hasValue
					? (field.defaultValues ?? [])
					: value === undefined || value === null
						? []
						: [String(value)];
			const selectedSet = new Set(selectedValues);

			const toggleOption = (optionValue: string) => {
				const next = new Set(selectedSet);
				if (next.has(optionValue)) {
					next.delete(optionValue);
				} else {
					next.add(optionValue);
				}
				updateValue(field.id, Array.from(next));
			};

			return (
				<div className="grid gap-2">
					<Label
						htmlFor={field.id}
						className="text-sm font-medium text-slate-700 dark:text-slate-200"
					>
						{field.label}
					</Label>
					<div className="grid gap-2 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-950">
						{field.options?.map((option) => (
							<label
								key={option.value}
								className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200"
							>
								<Checkbox
									checked={selectedSet.has(option.value)}
									onCheckedChange={() => toggleOption(option.value)}
								/>
								<span>{option.label}</span>
							</label>
						))}
					</div>
					{field.helper ? (
						<p className="text-xs text-slate-500 dark:text-slate-400">
							{field.helper}
						</p>
					) : null}
				</div>
			);
		}

		return (
			<div className="grid gap-2">
				<Label
					htmlFor={field.id}
					className="text-sm font-medium text-slate-700 dark:text-slate-200"
				>
					{field.label}
				</Label>
				{field.type === "textarea" ? (
					<Textarea
						id={field.id}
						className={`min-h-[96px] ${inputClassName}`}
						value={String(value ?? "")}
						placeholder={field.placeholder}
						onChange={(event) => updateValue(field.id, event.target.value)}
					/>
				) : field.type === "string-list" ? (
					<Textarea
						id={field.id}
						className={`min-h-[120px] ${inputClassName}`}
						value={
							Array.isArray(value)
								? value.map((entry) => String(entry)).join("\n")
								: String(value ?? "")
						}
						placeholder={field.placeholder}
						onChange={(event) => {
							const lines = event.target.value
								.split(/\r?\n/)
								.map((line) => line.trim())
								.filter(Boolean);
							updateValue(field.id, lines);
						}}
					/>
				) : field.type === "select" ? (
					<Select
						value={String(value ?? field.options?.[0]?.value ?? "")}
						onValueChange={(val) => updateValue(field.id, val)}
					>
						<SelectTrigger>
							<SelectValue placeholder={field.placeholder} />
						</SelectTrigger>
						<SelectContent>
							{field.options?.map((option) => (
								<SelectItem key={option.value} value={option.value}>
									{option.label}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				) : (
					<Input
						id={field.id}
						type={field.type}
						className={inputClassName}
						value={value === undefined || value === null ? "" : String(value)}
						placeholder={field.placeholder}
						onChange={(event) => updateValue(field.id, event.target.value)}
					/>
				)}
				{field.helper ? (
					<p className="text-xs text-slate-500 dark:text-slate-400">
						{field.helper}
					</p>
				) : null}
			</div>
		);
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-amber-50 text-slate-900 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 dark:text-slate-100">
			<div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 pb-16 pt-10">
				<header className="flex flex-wrap items-start justify-between gap-4">
					<div>
						<p className="text-sm uppercase tracking-[0.3em] text-slate-400 dark:text-slate-500">
							Settings
						</p>
						<h1 className="text-3xl font-semibold text-slate-900 dark:text-slate-100 sm:text-4xl">
							Fine-tune every download.
						</h1>
						<p className="mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
							Adjust tokens, folder formats, conversion rules, and metadata
							preferences without touching config files.
						</p>
					</div>
					<div className="flex items-center gap-3">
						<ThemeToggle />
						<Button variant="outline" className="gap-2" asChild>
							<a href="/">
								<ChevronLeft className="h-4 w-4" />
								Back
							</a>
						</Button>
						<Button
							className="gap-2"
							onClick={handleSave}
							disabled={saving || loading || hasInvalidMetadataCustomTagRules}
						>
							{saving ? (
								<Loader2 className="h-4 w-4 animate-spin" />
							) : (
								<Save className="h-4 w-4" />
							)}
							Save settings
						</Button>
					</div>
				</header>

				{message ? (
					<Alert
						className={
							message.type === "success"
								? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-300"
								: "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-300"
						}
					>
						<AlertTitle>
							{message.type === "success" ? "Saved" : "Error"}
						</AlertTitle>
						<AlertDescription>{message.text}</AlertDescription>
					</Alert>
				) : null}

				{loading ? (
					<Card className="border-slate-200/60 dark:border-slate-800/80 dark:bg-slate-950/40">
						<CardHeader>
							<CardTitle>Loading configuration...</CardTitle>
							<CardDescription>
								Fetching your current Apple Music downloader settings.
							</CardDescription>
						</CardHeader>
						<CardContent className="flex items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
							<Loader2 className="h-4 w-4 animate-spin" />
							Loading settings
						</CardContent>
					</Card>
				) : (
					<Tabs defaultValue={sectionIds[0]} className="w-full">
						<TabsList className="flex flex-wrap justify-start gap-2">
							{SECTIONS.map((section) => (
								<TabsTrigger
									key={section.id}
									value={section.id}
									className="gap-2"
								>
									{section.title}
									{section.badge ? (
										<Badge variant="secondary">{section.badge}</Badge>
									) : null}
								</TabsTrigger>
							))}
						</TabsList>

						{SECTIONS.map((section) => (
							<TabsContent key={section.id} value={section.id} className="mt-6">
								<Card className="border-slate-200/60 shadow-sm dark:border-slate-800/80 dark:bg-slate-950/40">
									<CardHeader>
										<div className="flex items-center justify-between">
											<div>
												<CardTitle className="text-lg">
													{section.title}
												</CardTitle>
												<CardDescription>{section.description}</CardDescription>
											</div>
											{section.badge ? (
												<Badge
													variant="outline"
													className="border-slate-200 text-slate-600 dark:border-slate-700 dark:text-slate-300"
												>
													{section.badge}
												</Badge>
											) : null}
										</div>
									</CardHeader>
									<CardContent className="grid gap-4">
										<div className="grid gap-4 md:grid-cols-2">
											{section.fields.map((field) => (
												<div key={field.id}>{renderField(field)}</div>
											))}
										</div>
										{section.id === "metadata" ? (
											<div className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950">
												<div className="flex flex-wrap items-start justify-between gap-3">
													<div>
														<p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
															Custom Metadata Tag Rules
														</p>
														<p className="text-xs text-slate-500 dark:text-slate-400">
															Add advanced KEY=VALUE tags and choose where each
															rule applies.
														</p>
													</div>
													<div className="flex flex-wrap items-center gap-2">
														<Button
															type="button"
															variant="outline"
															size="sm"
															onClick={addMetadataCustomTagRule}
															className="gap-1"
														>
															<Plus className="h-3.5 w-3.5" />
															Add rule
														</Button>
														<Button
															type="button"
															variant="secondary"
															size="sm"
															onClick={addAtmosAlbumVersionPreset}
														>
															Add Atmos AlbumVersion preset
														</Button>
													</div>
												</div>
												{metadataCustomTagRules.length === 0 ? (
													<p className="text-xs text-slate-500 dark:text-slate-400">
														No custom rules yet.
													</p>
												) : (
													<div className="grid gap-3">
														{metadataCustomTagRules.map((rule, index) => {
															const validation =
																metadataCustomTagRuleValidations[index] ?? {};
															return (
																<div
																	key={`metadata-custom-rule-${index}`}
																	className="grid gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-900/40"
																>
																	<div className="flex items-center justify-between">
																		<p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
																			Rule {index + 1}
																		</p>
																		<Button
																			type="button"
																			variant="ghost"
																			size="icon"
																			onClick={() =>
																				removeMetadataCustomTagRule(index)
																			}
																			className="h-7 w-7 text-slate-500 hover:text-rose-600 dark:text-slate-400 dark:hover:text-rose-400"
																		>
																			<Trash2 className="h-3.5 w-3.5" />
																		</Button>
																	</div>
																	<div className="grid gap-3 md:grid-cols-2">
																		<div className="grid gap-2">
																			<Label className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
																				Key
																			</Label>
																			<Input
																				value={rule.key}
																				onChange={(event) =>
																					updateMetadataCustomTagRule(index, {
																						key: event.target.value,
																					})
																				}
																				placeholder="ALBUMVERSION"
																				className="font-mono text-xs"
																			/>
																			{validation.keyError ? (
																				<p className="text-xs text-rose-600 dark:text-rose-400">
																					{validation.keyError}
																				</p>
																			) : null}
																		</div>
																		<div className="grid gap-2">
																			<Label className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
																				Value
																			</Label>
																			<Input
																				value={rule.value}
																				onChange={(event) =>
																					updateMetadataCustomTagRule(index, {
																						value: event.target.value,
																					})
																				}
																				placeholder="Dolby Atmos"
																				className="font-mono text-xs"
																			/>
																			{validation.valueError ? (
																				<p className="text-xs text-rose-600 dark:text-rose-400">
																					{validation.valueError}
																				</p>
																			) : null}
																		</div>
																	</div>
																	<div className="grid gap-3 md:grid-cols-2">
																		<div className="grid gap-2">
																			<Label className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
																				Containers
																			</Label>
																			<div className="grid gap-2">
																				{METADATA_CONTAINERS.map(
																					(container) => (
																						<label
																							key={`container-${container}-${index}`}
																							className="flex items-center gap-2 text-xs text-slate-700 dark:text-slate-200"
																						>
																							<Checkbox
																								checked={rule.containers.includes(
																									container,
																								)}
																								onCheckedChange={() =>
																									toggleMetadataCustomRuleContainer(
																										index,
																										container,
																									)
																								}
																							/>
																							<span>
																								{
																									METADATA_CONTAINER_SHORT_LABELS[
																										container
																									]
																								}
																							</span>
																						</label>
																					),
																				)}
																			</div>
																			{validation.containersError ? (
																				<p className="text-xs text-rose-600 dark:text-rose-400">
																					{validation.containersError}
																				</p>
																			) : null}
																		</div>
																		<div className="grid gap-2">
																			<Label className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
																				Source Formats
																			</Label>
																			<div className="grid gap-2">
																				{METADATA_SOURCE_FORMATS.map(
																					(sourceFormat) => (
																						<label
																							key={`source-format-${sourceFormat}-${index}`}
																							className="flex items-center gap-2 text-xs text-slate-700 dark:text-slate-200"
																						>
																							<Checkbox
																								checked={rule.sourceFormats.includes(
																									sourceFormat,
																								)}
																								onCheckedChange={() =>
																									toggleMetadataCustomRuleSourceFormat(
																										index,
																										sourceFormat,
																									)
																								}
																							/>
																							<span>
																								{
																									METADATA_SOURCE_FORMAT_LABELS[
																										sourceFormat
																									]
																								}
																							</span>
																						</label>
																					),
																				)}
																			</div>
																			{validation.sourceFormatsError ? (
																				<p className="text-xs text-rose-600 dark:text-rose-400">
																					{validation.sourceFormatsError}
																				</p>
																			) : null}
																		</div>
																	</div>
																</div>
															);
														})}
													</div>
												)}
												{hasInvalidMetadataCustomTagRules ? (
													<p className="text-xs text-rose-600 dark:text-rose-400">
														Resolve validation errors before saving settings.
													</p>
												) : null}
											</div>
										) : null}
										<Separator />
										<div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
											<span>Changes are saved to config.yaml</span>
											<span>{Object.keys(config).length} fields loaded</span>
										</div>
									</CardContent>
								</Card>
							</TabsContent>
						))}
					</Tabs>
				)}
			</div>
		</div>
	);
}
