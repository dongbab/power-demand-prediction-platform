import { defineConfig } from "vite";
import { sveltekit } from "@sveltejs/kit/vite";

export default defineConfig({
    plugins: [sveltekit()],
    server: {
        host: "0.0.0.0",
        port: 32376,
        proxy: {
            "/api": {
                target: "http://127.0.0.1:32375",
                changeOrigin: true,
            },
        },
    },
});
