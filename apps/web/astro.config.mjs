// @ts-check

import react from "@astrojs/react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "astro/config";

// https://astro.build/config
export default defineConfig({
	vite: {
		plugins: [tailwindcss()],
		server: {
			proxy: {
				"/api": "http://localhost:3001",
			},
		},
	},

	integrations: [react()],
});
