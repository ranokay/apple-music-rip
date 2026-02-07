import { describe, expect, it } from "bun:test";
import {
	createDefaultMetadataProfiles,
	KNOWN_METADATA_TAG_IDS_BY_CONTAINER,
	resolveMetadataDefaultsFromConfig,
	resolveMetadataProfilesForRequest,
} from "./metadata-profiles";

describe("metadata profile defaults", () => {
	it("enables all known tags when config fields are absent", () => {
		const profiles = resolveMetadataDefaultsFromConfig({});
		expect(profiles.m4a).toEqual([...KNOWN_METADATA_TAG_IDS_BY_CONTAINER.m4a]);
		expect(profiles.flac).toEqual([...KNOWN_METADATA_TAG_IDS_BY_CONTAINER.flac]);
	});

	it("normalizes configured tags by container", () => {
		const profiles = resolveMetadataDefaultsFromConfig({
			"metadata-tags-m4a": ["TITLE", "artist", "artist", "unknown"],
			"metadata-tags-flac": "lyrics,cover,itunes_album_id,release_time,LYRICS",
		});

		expect(profiles.m4a).toEqual(["title", "artist"]);
		expect(profiles.flac).toEqual(["lyrics", "cover"]);
	});

	it("applies container-specific allowlists", () => {
		const profiles = resolveMetadataDefaultsFromConfig({
			"metadata-tags-m4a": ["release_type", "itunes_album_id"],
			"metadata-tags-flac":
				"release_type,original_date,loudness,itunes_album_id,release_time",
		});

		expect(profiles.m4a).toEqual(["release_type", "itunes_album_id"]);
		expect(profiles.flac).toEqual(["original_date", "release_type", "loudness"]);
	});
});

describe("request override resolution", () => {
	it("uses defaults when override is missing or use_defaults=true", () => {
		const config = {
			"metadata-tags-m4a": ["title", "artist"],
		};

		const missing = resolveMetadataProfilesForRequest(undefined, config);
		expect(missing.error).toBeUndefined();
		expect(missing.profiles.m4a).toEqual(["title", "artist"]);

		const explicitDefaults = resolveMetadataProfilesForRequest(
			{ use_defaults: true, by_container: { m4a: ["album"] } },
			config,
		);
		expect(explicitDefaults.error).toBeUndefined();
		expect(explicitDefaults.profiles.m4a).toEqual(["title", "artist"]);
	});

	it("overrides only specified containers when use_defaults=false", () => {
		const defaults = createDefaultMetadataProfiles();
		const result = resolveMetadataProfilesForRequest(
			{
				use_defaults: false,
				by_container: {
					m4a: ["title", "album"],
				},
			},
			{},
		);

		expect(result.error).toBeUndefined();
		expect(result.profiles.m4a).toEqual(["title", "album"]);
		expect(result.profiles.flac).toEqual(defaults.flac);
	});

	it("keeps config defaults unchanged across override resolution calls", () => {
		const config = {
			"metadata-tags-m4a": ["title"],
			"metadata-tags-flac": ["artist"],
		};

		const override = resolveMetadataProfilesForRequest(
			{
				use_defaults: false,
				by_container: {
					m4a: ["album"],
				},
			},
			config,
		);
		expect(override.error).toBeUndefined();
		expect(override.profiles.m4a).toEqual(["album"]);
		expect(override.profiles.flac).toEqual(["artist"]);

		const defaults = resolveMetadataProfilesForRequest(undefined, config);
		expect(defaults.error).toBeUndefined();
		expect(defaults.profiles.m4a).toEqual(["title"]);
		expect(defaults.profiles.flac).toEqual(["artist"]);
	});

	it("rejects unknown tag IDs in override", () => {
		const result = resolveMetadataProfilesForRequest(
			{
				use_defaults: false,
				by_container: {
					flac: ["title", "bad_tag"],
				},
			},
			{},
		);

		expect(result.error).toContain("Unknown metadata tags for flac");
		expect(result.error).toContain("bad_tag");
	});

	it("rejects malformed by_container payloads", () => {
		const malformed = resolveMetadataProfilesForRequest(
			{ use_defaults: false, by_container: "not-an-object" },
			{},
		);
		expect(malformed.error).toBe("Invalid metadata profile override by container.");
	});

	it("rejects unknown metadata containers", () => {
		const malformed = resolveMetadataProfilesForRequest(
			{
				use_defaults: false,
				by_container: { m4a: ["title"], invalid: ["artist"] },
			},
			{},
		);
		expect(malformed.error).toContain("Unknown metadata containers: invalid");
	});
});
