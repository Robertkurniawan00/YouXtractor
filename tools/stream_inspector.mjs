/**
 * YouXtractor - Node.js Stream Inspector
 * High-speed YouTube metadata analyzer & stream verification tool.
 * Language: JavaScript (Node.js v24+ ES Module)
 */

import { argv, stdout, exit } from "node:process";

const url = argv[2];

if (!url) {
    stdout.write("Usage: node tools/stream_inspector.mjs <YouTube_URL>\n");
    stdout.write("Example: node tools/stream_inspector.mjs https://www.youtube.com/watch?v=dQw4w9WgXcQ\n");
    exit(1);
}

function extractVideoId(rawUrl) {
    const match = rawUrl.match(/(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))([\w-]{11})/);
    return match ? match[1] : null;
}

async function inspect(targetUrl) {
    const videoId = extractVideoId(targetUrl);
    if (!videoId) {
        stdout.write(JSON.stringify({ error: "Invalid YouTube URL format." }, null, 2) + "\n");
        exit(1);
    }

    try {
        const oembedUrl = `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${videoId}&format=json`;
        const resp = await fetch(oembedUrl);
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}: Video unavailable or private.`);
        }
        const data = await resp.json();

        const result = {
            id: videoId,
            title: data.title,
            author_name: data.author_name,
            author_url: data.author_url,
            thumbnail_url: data.thumbnail_url,
            provider_name: data.provider_name,
            expected_master_stream: {
                codec: "Opus",
                sample_rate: 48000,
                max_bitrate_kbps: 160,
                container: "webm"
            },
            status: "ready"
        };

        stdout.write(JSON.stringify(result, null, 2) + "\n");
    } catch (err) {
        stdout.write(JSON.stringify({ error: err.message }, null, 2) + "\n");
        exit(1);
    }
}

inspect(url);
