import { describe, expect, it } from "bun:test";
import {
	buildMetadataProfileOverridePayload,
	cloneMetadataByContainer,
	createEmptyMetadataCustomTagRule,
	createDefaultMetadataByContainer,
	DEFAULT_METADATA_TAGS_BY_CONTAINER,
	isMetadataCustomTagRuleValid,
	METADATA_TAG_IDS_BY_CONTAINER,
	normalizeMetadataTags,
	resolveMetadataCustomTagRulesFromConfig,
	resolveMetadataTagsFromConfig,
	serializeMetadataCustomTagRulesForConfig,
	validateMetadataCustomTagRule,
} from "./metadataProfiles";

describe("metadataProfiles helpers", () => {
	it("normalizes tags from arrays and strings", () => {
		expect(normalizeMetadataTags(["TITLE", "artist", "artist", "bad"], "m4a"))
			.toEqual(["title", "artist"]);
		expect(normalizeMetadataTags("lyrics,cover,LYRICS,unknown", "flac")).toEqual([
			"lyrics",
			"cover",
		]);
		expect(
			normalizeMetadataTags("itunes_album_id,release_time,release_type", "flac"),
		).toEqual(["release_type"]);
	});

	it("resolves config with container defaults", () => {
		const resolved = resolveMetadataTagsFromConfig({
			"metadata-tags-m4a": ["title", "album", "title"],
			"metadata-tags-flac": "lyrics,cover,itunes_album_id",
		});

		expect(resolved.m4a).toEqual(["title", "album"]);
		expect(resolved.flac).toEqual(["lyrics", "cover"]);
	});

	it("uses container-specific default tag sets", () => {
		const defaults = createDefaultMetadataByContainer();
		expect(defaults.m4a).toEqual(DEFAULT_METADATA_TAGS_BY_CONTAINER.m4a);
		expect(defaults.flac).toEqual(DEFAULT_METADATA_TAGS_BY_CONTAINER.flac);
		expect(defaults.m4a).toContain("itunes_album_id");
		expect(defaults.flac).not.toContain("itunes_album_id");
		expect(defaults.m4a).not.toContain("loudness");
		expect(defaults.flac).toContain("loudness");
		expect(defaults.m4a).not.toContain("original_date");
		expect(defaults.flac).toContain("original_date");
		expect(defaults.m4a).toContain("release_type");
		expect(defaults.flac).toContain("release_type");
	});

	it("builds override payload only when defaults are disabled", () => {
		const overrideByContainer = createDefaultMetadataByContainer();
		overrideByContainer.m4a = ["title", "album"];
		overrideByContainer.flac = ["artist"];

		expect(
			buildMetadataProfileOverridePayload(true, overrideByContainer),
		).toBeUndefined();

		const payload = buildMetadataProfileOverridePayload(
			false,
			overrideByContainer,
		);
		expect(payload).toEqual({
			use_defaults: false,
			by_container: {
				m4a: ["title", "album"],
				flac: ["artist"],
			},
		});
	});

	it("clones per-container state defensively", () => {
		const defaults = createDefaultMetadataByContainer();
		const clone = cloneMetadataByContainer(defaults);
		clone.m4a = ["title"];

		expect(defaults.m4a).not.toEqual(clone.m4a);
		expect(defaults.m4a.length).toBeGreaterThan(clone.m4a.length);
	});

	it("normalizes custom metadata rules from config", () => {
		const rules = resolveMetadataCustomTagRulesFromConfig({
			"metadata-custom-tag-rules": [
				{
					key: " albumversion ",
					value: " Dolby Atmos ",
					containers: ["M4A", "m4a", "bad"],
					"source-formats": "atmos,aac,ATmos",
				},
			],
		});

		expect(rules).toEqual([
			{
				key: "ALBUMVERSION",
				value: "Dolby Atmos",
				containers: ["m4a"],
				sourceFormats: ["aac", "atmos"],
			},
		]);
	});

	it("validates custom metadata rule rows", () => {
		const invalid = validateMetadataCustomTagRule(
			createEmptyMetadataCustomTagRule(),
		);
		expect(isMetadataCustomTagRuleValid(invalid)).toBe(false);
		expect(invalid.keyError).toBeDefined();
		expect(invalid.valueError).toBeDefined();
		expect(invalid.containersError).toBeDefined();
		expect(invalid.sourceFormatsError).toBeDefined();

		const valid = validateMetadataCustomTagRule({
			key: "ALBUMVERSION",
			value: "Dolby Atmos",
			containers: ["m4a"],
			sourceFormats: ["atmos"],
		});
		expect(isMetadataCustomTagRuleValid(valid)).toBe(true);
	});

	it("serializes custom metadata rules for config saves", () => {
		const serialized = serializeMetadataCustomTagRulesForConfig([
			{
				key: "albumversion",
				value: " Dolby Atmos ",
				containers: ["flac", "m4a", "m4a"],
				sourceFormats: ["aac", "atmos", "aac"],
			},
		]);

		expect(serialized).toEqual([
			{
				key: "ALBUMVERSION",
				value: "Dolby Atmos",
				containers: ["m4a", "flac"],
				"source-formats": ["aac", "atmos"],
			},
		]);
	});

	it("keeps container tag id lists aligned with expected differences", () => {
		expect(METADATA_TAG_IDS_BY_CONTAINER.m4a).toContain("itunes_album_id");
		expect(METADATA_TAG_IDS_BY_CONTAINER.m4a).toContain("itunes_artist_id");
		expect(METADATA_TAG_IDS_BY_CONTAINER.flac).not.toContain("itunes_album_id");
		expect(METADATA_TAG_IDS_BY_CONTAINER.flac).not.toContain("itunes_artist_id");
		expect(METADATA_TAG_IDS_BY_CONTAINER.m4a).not.toContain("release_time");
		expect(METADATA_TAG_IDS_BY_CONTAINER.flac).not.toContain("release_time");
	});
});
