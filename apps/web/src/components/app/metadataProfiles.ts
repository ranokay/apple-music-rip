export type MetadataContainer = "m4a" | "flac";
export type MetadataSourceFormat = "lossless" | "hires" | "aac" | "atmos";

export const METADATA_CONTAINERS: MetadataContainer[] = ["m4a", "flac"];
export const METADATA_SOURCE_FORMATS: MetadataSourceFormat[] = [
	"lossless",
	"hires",
	"aac",
	"atmos",
];
export const METADATA_SOURCE_FORMAT_LABELS: Record<MetadataSourceFormat, string> = {
	lossless: "Lossless (ALAC)",
	hires: "Hi-Res Lossless",
	aac: "AAC",
	atmos: "Dolby Atmos",
};
export const METADATA_CONTAINER_SHORT_LABELS: Record<MetadataContainer, string> = {
	m4a: "M4A",
	flac: "FLAC",
};
const CUSTOM_METADATA_TAG_KEY_RE = /^[A-Z0-9_:-]{1,64}$/;
export const MAX_CUSTOM_METADATA_TAG_VALUE_LENGTH = 512;
export const METADATA_CUSTOM_TAG_RULES_KEY = "metadata-custom-tag-rules";

const METADATA_TAG_LABELS: Record<string, string> = {
	title: "Title",
	title_sort: "Title Sort",
	artist: "Artist",
	artist_sort: "Artist Sort",
	album: "Album",
	album_sort: "Album Sort",
	album_artist: "Album Artist",
	album_artist_sort: "Album Artist Sort",
	composer: "Composer",
	composer_sort: "Composer Sort",
	genre: "Genre",
	track_number: "Track Number",
	track_total: "Track Total",
	disc_number: "Disc Number",
	disc_total: "Disc Total",
	release_date: "Release Date",
	original_date: "Original Date",
	release_type: "Release Type",
	isrc: "ISRC",
	upc: "UPC",
	label: "Label",
	publisher: "Publisher",
	copyright: "Copyright",
	advisory: "Advisory",
	itunes_album_id: "iTunes Album ID",
	itunes_artist_id: "iTunes Artist ID",
	album_version: "Edition (Album Version)",
	lyrics: "Lyrics",
	cover: "Cover",
	performer: "Performer",
	loudness: "Loudness (ReplayGain / R128)",
};

export const METADATA_TAG_IDS_BY_CONTAINER: Record<MetadataContainer, string[]> = {
	m4a: [
		"title",
		"title_sort",
		"artist",
		"artist_sort",
		"album",
		"album_sort",
		"album_artist",
		"album_artist_sort",
		"composer",
		"composer_sort",
		"genre",
		"track_number",
		"track_total",
		"disc_number",
		"disc_total",
		"release_date",
		"release_type",
		"isrc",
		"upc",
		"label",
		"publisher",
		"copyright",
		"advisory",
		"itunes_album_id",
		"itunes_artist_id",
		"album_version",
		"lyrics",
		"cover",
		"performer",
	],
	flac: [
		"title",
		"title_sort",
		"artist",
		"artist_sort",
		"album",
		"album_sort",
		"album_artist",
		"album_artist_sort",
		"composer",
		"composer_sort",
		"genre",
		"track_number",
		"track_total",
		"disc_number",
		"disc_total",
		"release_date",
		"original_date",
		"release_type",
		"isrc",
		"upc",
		"label",
		"publisher",
		"copyright",
		"advisory",
		"album_version",
		"lyrics",
		"cover",
		"performer",
		"loudness",
	],
};

type MetadataTagOption = {
	value: string;
	label: string;
};

export const METADATA_TAG_OPTIONS_BY_CONTAINER: Record<
	MetadataContainer,
	MetadataTagOption[]
> = {
	m4a: METADATA_TAG_IDS_BY_CONTAINER.m4a.map((id) => ({
		value: id,
		label: METADATA_TAG_LABELS[id] ?? id,
	})),
	flac: METADATA_TAG_IDS_BY_CONTAINER.flac.map((id) => ({
		value: id,
		label: METADATA_TAG_LABELS[id] ?? id,
	})),
};

export const DEFAULT_METADATA_TAGS_BY_CONTAINER: Record<
	MetadataContainer,
	string[]
> = {
	m4a: [...METADATA_TAG_IDS_BY_CONTAINER.m4a],
	flac: [...METADATA_TAG_IDS_BY_CONTAINER.flac],
};

const METADATA_TAG_SET_BY_CONTAINER: Record<MetadataContainer, Set<string>> = {
	m4a: new Set(METADATA_TAG_IDS_BY_CONTAINER.m4a),
	flac: new Set(METADATA_TAG_IDS_BY_CONTAINER.flac),
};

export const METADATA_CONFIG_KEYS: Record<MetadataContainer, string> = {
	m4a: "metadata-tags-m4a",
	flac: "metadata-tags-flac",
};

export const METADATA_CONTAINER_LABELS: Record<MetadataContainer, string> = {
	m4a: "M4A / MP4 Tags",
	flac: "FLAC Tags",
};

export type MetadataByContainer = Record<MetadataContainer, string[]>;
export type MetadataCustomTagRule = {
	key: string;
	value: string;
	containers: MetadataContainer[];
	sourceFormats: MetadataSourceFormat[];
};
export type MetadataCustomTagRuleValidation = {
	keyError?: string;
	valueError?: string;
	containersError?: string;
	sourceFormatsError?: string;
};

export function metadataTagOptionsForContainer(
	container: MetadataContainer,
): MetadataTagOption[] {
	return METADATA_TAG_OPTIONS_BY_CONTAINER[container];
}

export function cloneMetadataByContainer(
	source: MetadataByContainer,
): MetadataByContainer {
	return {
		m4a: [...source.m4a],
		flac: [...source.flac],
	};
}

export function createDefaultMetadataByContainer(): MetadataByContainer {
	return {
		m4a: [...DEFAULT_METADATA_TAGS_BY_CONTAINER.m4a],
		flac: [...DEFAULT_METADATA_TAGS_BY_CONTAINER.flac],
	};
}

export function normalizeMetadataTags(
	rawValue: unknown,
	container: MetadataContainer,
): string[] {
	const rawTags = Array.isArray(rawValue)
		? rawValue
				.map((entry) => String(entry).trim().toLowerCase())
				.filter(Boolean)
		: typeof rawValue === "string"
			? rawValue
					.split(",")
					.map((entry) => entry.trim().toLowerCase())
					.filter(Boolean)
			: [];
	const deduped: string[] = [];
	const seen = new Set<string>();
	const allowSet = METADATA_TAG_SET_BY_CONTAINER[container];
	const order = METADATA_TAG_IDS_BY_CONTAINER[container];
	for (const tag of rawTags) {
		if (!allowSet.has(tag) || seen.has(tag)) continue;
		seen.add(tag);
	}
	for (const tag of order) {
		if (seen.has(tag)) deduped.push(tag);
	}
	return deduped;
}

export function resolveMetadataTagsFromConfig(
	config: Record<string, unknown> | null | undefined,
): MetadataByContainer {
	const resolved = createDefaultMetadataByContainer();
	if (!config) return resolved;
	for (const container of METADATA_CONTAINERS) {
		const key = METADATA_CONFIG_KEYS[container];
		if (!Object.prototype.hasOwnProperty.call(config, key)) continue;
		resolved[container] = normalizeMetadataTags(config[key], container);
	}
	return resolved;
}

export function buildMetadataProfileOverridePayload(
	metadataUseDefaults: boolean,
	metadataOverrideByContainer: MetadataByContainer,
):
	| {
			use_defaults: false;
			by_container: Partial<Record<MetadataContainer, string[]>>;
	  }
	| undefined {
	if (metadataUseDefaults) return undefined;
	return {
		use_defaults: false,
		by_container: {
			m4a: [...metadataOverrideByContainer.m4a],
			flac: [...metadataOverrideByContainer.flac],
		},
	};
}

function normalizeStringList(raw: unknown): string[] {
	if (Array.isArray(raw)) {
		return raw.map((entry) => String(entry).trim()).filter(Boolean);
	}
	if (typeof raw === "string") {
		return raw
			.split(",")
			.map((entry) => entry.trim())
			.filter(Boolean);
	}
	return [];
}

function normalizeContainerList(raw: unknown): MetadataContainer[] {
	const normalized = new Set<MetadataContainer>();
	for (const value of normalizeStringList(raw)) {
		const lower = value.toLowerCase();
		if (!METADATA_CONTAINERS.includes(lower as MetadataContainer)) continue;
		normalized.add(lower as MetadataContainer);
	}
	return METADATA_CONTAINERS.filter((container) => normalized.has(container));
}

function normalizeSourceFormatList(raw: unknown): MetadataSourceFormat[] {
	const normalized = new Set<MetadataSourceFormat>();
	for (const value of normalizeStringList(raw)) {
		const lower = value.toLowerCase();
		if (!METADATA_SOURCE_FORMATS.includes(lower as MetadataSourceFormat))
			continue;
		normalized.add(lower as MetadataSourceFormat);
	}
	return METADATA_SOURCE_FORMATS.filter((format) => normalized.has(format));
}

export function createEmptyMetadataCustomTagRule(): MetadataCustomTagRule {
	return {
		key: "",
		value: "",
		containers: [],
		sourceFormats: [],
	};
}

export function normalizeMetadataCustomTagRule(
	raw: unknown,
): MetadataCustomTagRule {
	if (!raw || typeof raw !== "object") {
		return createEmptyMetadataCustomTagRule();
	}
	const row = raw as Record<string, unknown>;
	return {
		key: String(row.key ?? "")
			.trim()
			.toUpperCase(),
		value: String(row.value ?? "").trim(),
		containers: normalizeContainerList(row.containers),
		sourceFormats: normalizeSourceFormatList(
			row["source-formats"] ?? row.sourceFormats,
		),
	};
}

export function resolveMetadataCustomTagRulesFromConfig(
	config: Record<string, unknown> | null | undefined,
): MetadataCustomTagRule[] {
	if (!config) return [];
	const raw = config[METADATA_CUSTOM_TAG_RULES_KEY];
	if (!Array.isArray(raw)) return [];
	return raw.map((entry) => normalizeMetadataCustomTagRule(entry));
}

export function validateMetadataCustomTagRule(
	row: MetadataCustomTagRule,
): MetadataCustomTagRuleValidation {
	const validation: MetadataCustomTagRuleValidation = {};
	if (!CUSTOM_METADATA_TAG_KEY_RE.test(row.key)) {
		validation.keyError = "Key must match ^[A-Z0-9_:-]{1,64}$.";
	}
	if (!row.value) {
		validation.valueError = "Value is required.";
	} else if (row.value.length > MAX_CUSTOM_METADATA_TAG_VALUE_LENGTH) {
		validation.valueError = `Value must be ${MAX_CUSTOM_METADATA_TAG_VALUE_LENGTH} characters or fewer.`;
	}
	if (row.containers.length === 0) {
		validation.containersError = "Select at least one container.";
	}
	if (row.sourceFormats.length === 0) {
		validation.sourceFormatsError = "Select at least one source format.";
	}
	return validation;
}

export function isMetadataCustomTagRuleValid(
	validation: MetadataCustomTagRuleValidation,
): boolean {
	return !Object.values(validation).some(Boolean);
}

export function serializeMetadataCustomTagRulesForConfig(
	rules: MetadataCustomTagRule[],
): Array<{
	key: string;
	value: string;
	containers: MetadataContainer[];
	"source-formats": MetadataSourceFormat[];
}> {
	return rules.map((row) => ({
		key: row.key.trim().toUpperCase(),
		value: row.value.trim(),
		containers: normalizeContainerList(row.containers),
		"source-formats": normalizeSourceFormatList(row.sourceFormats),
	}));
}
