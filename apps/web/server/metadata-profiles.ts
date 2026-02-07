export const DOWNLOAD_FORMATS = ["lossless", "hires", "aac", "atmos"] as const;
export type DownloadFormat = (typeof DOWNLOAD_FORMATS)[number];

export const METADATA_CONTAINERS = ["m4a", "flac"] as const;
export type MetadataContainer = (typeof METADATA_CONTAINERS)[number];

export const METADATA_CONFIG_KEY_BY_CONTAINER: Record<MetadataContainer, string> = {
	m4a: "metadata-tags-m4a",
	flac: "metadata-tags-flac",
};

export const KNOWN_METADATA_TAG_IDS_BY_CONTAINER: Record<
	MetadataContainer,
	readonly string[]
> = {
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

export const KNOWN_METADATA_TAG_IDS = Array.from(
	new Set([
		...KNOWN_METADATA_TAG_IDS_BY_CONTAINER.m4a,
		...KNOWN_METADATA_TAG_IDS_BY_CONTAINER.flac,
	]),
) as string[];

const KNOWN_METADATA_TAG_SET_BY_CONTAINER: Record<MetadataContainer, Set<string>> =
	{
		m4a: new Set(KNOWN_METADATA_TAG_IDS_BY_CONTAINER.m4a),
		flac: new Set(KNOWN_METADATA_TAG_IDS_BY_CONTAINER.flac),
	};

export type MetadataOverrideInput = {
	use_defaults?: boolean;
	by_container?: Partial<Record<MetadataContainer, unknown>>;
};

export type ResolvedMetadataProfiles = Record<MetadataContainer, string[]>;

function cloneMetadataProfiles(
	source: ResolvedMetadataProfiles,
): ResolvedMetadataProfiles {
	return {
		m4a: [...source.m4a],
		flac: [...source.flac],
	};
}

export function createDefaultMetadataProfiles(): ResolvedMetadataProfiles {
	return {
		m4a: [...KNOWN_METADATA_TAG_IDS_BY_CONTAINER.m4a],
		flac: [...KNOWN_METADATA_TAG_IDS_BY_CONTAINER.flac],
	};
}

export function normalizeMetadataTagIDs(
	input: unknown,
	container: MetadataContainer,
) {
	const invalid: string[] = [];
	const normalized = new Set<string>();
	const rawList = Array.isArray(input)
		? input
		: typeof input === "string"
			? input
					.split(",")
					.map((entry) => entry.trim())
					.filter(Boolean)
			: [];

	for (const raw of rawList) {
		const value = String(raw).trim().toLowerCase();
		if (!value) continue;
		if (!KNOWN_METADATA_TAG_SET_BY_CONTAINER[container].has(value)) {
			invalid.push(value);
			continue;
		}
		normalized.add(value);
	}

	return {
		tags: KNOWN_METADATA_TAG_IDS_BY_CONTAINER[container].filter((id) =>
			normalized.has(id),
		),
		invalid,
	};
}

export function resolveMetadataDefaultsFromConfig(
	config: Record<string, unknown>,
): ResolvedMetadataProfiles {
	const profiles = createDefaultMetadataProfiles();
	for (const container of METADATA_CONTAINERS) {
		const key = METADATA_CONFIG_KEY_BY_CONTAINER[container];
		if (!Object.hasOwn(config, key)) continue;
		const { tags } = normalizeMetadataTagIDs(config[key], container);
		profiles[container] = tags;
	}
	return profiles;
}

export function resolveMetadataProfilesForRequest(
	overrideInput: unknown,
	config: Record<string, unknown>,
): { profiles: ResolvedMetadataProfiles; error?: string } {
	const defaults = resolveMetadataDefaultsFromConfig(config);
	if (!overrideInput) return { profiles: defaults };
	if (typeof overrideInput !== "object" || overrideInput === null) {
		return { profiles: defaults, error: "Invalid metadata profile override." };
	}

	const override = overrideInput as MetadataOverrideInput;
	if (override.use_defaults !== false) {
		return { profiles: defaults };
	}

	const byContainer = override.by_container;
	if (
		byContainer !== undefined &&
		(typeof byContainer !== "object" || byContainer === null)
	) {
		return {
			profiles: defaults,
			error: "Invalid metadata profile override by container.",
		};
	}

	const profiles = cloneMetadataProfiles(defaults);
	if (!byContainer) {
		return { profiles };
	}

	const invalidContainers = Object.keys(byContainer).filter(
		(key) => !METADATA_CONTAINERS.includes(key as MetadataContainer),
	);
	if (invalidContainers.length > 0) {
		return {
			profiles: defaults,
			error: `Unknown metadata containers: ${invalidContainers.join(", ")}`,
		};
	}

	for (const container of METADATA_CONTAINERS) {
		if (!Object.hasOwn(byContainer, container)) continue;
		const value = byContainer[container];
		const normalized = normalizeMetadataTagIDs(value, container);
		if (normalized.invalid.length > 0) {
			return {
				profiles: defaults,
				error: `Unknown metadata tags for ${container}: ${normalized.invalid.join(", ")}`,
			};
		}
		profiles[container] = normalized.tags;
	}
	return { profiles };
}
