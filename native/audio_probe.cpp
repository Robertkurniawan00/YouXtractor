#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cstring>
#include <cstdint>
#include <iomanip>

struct AudioMetadata {
    std::string format = "unknown";
    bool valid = false;
    std::string title = "";
    std::string artist = "";
    std::string album = "";
    std::string year = "";
    bool has_cover_art = false;
    std::string cover_mime = "";
    size_t cover_size_bytes = 0;
    int sample_rate = 0;
    int channels = 0;
    int bitrate_kbps = 0;
    bool is_vbr = false;
    std::string encoder = "";
    size_t file_size_bytes = 0;
};

// Safe Big-Endian Syncsafe Integer unpacker (ID3v2)
static uint32_t unpack_syncsafe(const uint8_t* buf) {
    return ((buf[0] & 0x7F) << 21) |
           ((buf[1] & 0x7F) << 14) |
           ((buf[2] & 0x7F) << 7)  |
           (buf[3] & 0x7F);
}

// Safe Big-Endian 32-bit Integer unpacker
static uint32_t unpack_be32(const uint8_t* buf) {
    return (uint32_t(buf[0]) << 24) |
           (uint32_t(buf[1]) << 16) |
           (uint32_t(buf[2]) << 8)  |
           uint32_t(buf[3]);
}

// Clean string from ID3 text encoding byte
static std::string decode_id3_text(const uint8_t* data, size_t length) {
    if (length <= 1) return "";
    uint8_t encoding = data[0];
    const uint8_t* text_data = data + 1;
    size_t text_len = length - 1;

    std::string result = "";
    if (encoding == 0 || encoding == 3) { // ISO-8859-1 or UTF-8
        for (size_t i = 0; i < text_len; ++i) {
            if (text_data[i] == 0) break;
            result += static_cast<char>(text_data[i]);
        }
    } else if (encoding == 1 || encoding == 2) { // UTF-16
        // Simple ascii/utf-8 projection from utf-16le
        size_t start = (text_len >= 2 && text_data[0] == 0xFF && text_data[1] == 0xFE) ? 2 : 0;
        for (size_t i = start; i + 1 < text_len; i += 2) {
            uint16_t ch = text_data[i] | (text_data[i + 1] << 8);
            if (ch == 0) break;
            if (ch < 128) result += static_cast<char>(ch);
        }
    }
    return result;
}

static void parse_id3v2(std::ifstream& file, AudioMetadata& meta) {
    uint8_t header[10];
    file.seekg(0, std::ios::beg);
    if (!file.read(reinterpret_cast<char*>(header), 10)) return;

    if (header[0] != 'I' || header[1] != 'D' || header[2] != '3') return;

    uint32_t tag_size = unpack_syncsafe(header + 6);
    if (tag_size == 0 || tag_size > 50 * 1024 * 1024) return;

    std::vector<uint8_t> tag_buffer(tag_size);
    if (!file.read(reinterpret_cast<char*>(tag_buffer.data()), tag_size)) return;

    size_t offset = 0;
    while (offset + 10 < tag_size) {
        // Frame ID (4 bytes)
        char frame_id[5] = {0};
        std::memcpy(frame_id, tag_buffer.data() + offset, 4);

        if (frame_id[0] < 'A' || frame_id[0] > 'Z') break; // Padding reached

        uint32_t frame_len = unpack_be32(tag_buffer.data() + offset + 4);
        if (header[3] == 4) { // ID3v2.4 uses syncsafe for frame sizes
            frame_len = unpack_syncsafe(tag_buffer.data() + offset + 4);
        }

        offset += 10;
        if (offset + frame_len > tag_size) break;

        const uint8_t* frame_data = tag_buffer.data() + offset;

        if (std::strcmp(frame_id, "TIT2") == 0) {
            meta.title = decode_id3_text(frame_data, frame_len);
        } else if (std::strcmp(frame_id, "TPE1") == 0) {
            meta.artist = decode_id3_text(frame_data, frame_len);
        } else if (std::strcmp(frame_id, "TALB") == 0) {
            meta.album = decode_id3_text(frame_data, frame_len);
        } else if (std::strcmp(frame_id, "TYER") == 0 || std::strcmp(frame_id, "TDRC") == 0) {
            meta.year = decode_id3_text(frame_data, frame_len);
        } else if (std::strcmp(frame_id, "APIC") == 0) {
            meta.has_cover_art = true;
            meta.cover_size_bytes = frame_len;
            if (frame_len > 2) {
                // Parse MIME type
                size_t p = 1;
                std::string mime = "";
                while (p < frame_len && frame_data[p] != 0) {
                    mime += static_cast<char>(frame_data[p++]);
                }
                meta.cover_mime = mime.empty() ? "image/jpeg" : mime;
            }
        }

        offset += frame_len;
    }
}

static void parse_mp3_frames(std::ifstream& file, AudioMetadata& meta) {
    file.seekg(0, std::ios::end);
    meta.file_size_bytes = file.tellg();
    file.seekg(0, std::ios::beg);

    parse_id3v2(file, meta);

    // Scan for first MPEG audio sync word (0xFFE or 0xFFF)
    const size_t scan_limit = std::min<size_t>(meta.file_size_bytes, 1024 * 1024);
    std::vector<uint8_t> scan_buf(scan_limit);
    file.seekg(0, std::ios::beg);
    file.read(reinterpret_cast<char*>(scan_buf.data()), scan_limit);

    const int bitrates[16] = {0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0};
    const int sample_rates[4] = {44100, 48000, 32000, 0};

    for (size_t i = 0; i + 4 < scan_limit; ++i) {
        if (scan_buf[i] == 0xFF && (scan_buf[i + 1] & 0xE0) == 0xE0) {
            uint8_t b1 = scan_buf[i + 1];
            uint8_t b2 = scan_buf[i + 2];
            uint8_t b3 = scan_buf[i + 3];

            int mpeg_ver = (b1 >> 3) & 0x03; // 3 = MPEG-1
            int layer = (b1 >> 1) & 0x03;    // 1 = Layer III
            if (mpeg_ver != 3 || layer != 1) continue;

            int br_idx = (b2 >> 4) & 0x0F;
            int sr_idx = (b2 >> 2) & 0x03;
            int channel_mode = (b3 >> 6) & 0x03;

            if (br_idx == 0 || br_idx == 15 || sr_idx == 3) continue;

            meta.format = "mp3";
            meta.valid = true;
            meta.sample_rate = sample_rates[sr_idx];
            meta.bitrate_kbps = bitrates[br_idx];
            meta.channels = (channel_mode == 3) ? 1 : 2;

            // Check Xing / Info / LAME tag offset (36 bytes after header for stereo)
            size_t xing_off = i + 4 + (meta.channels == 2 ? 32 : 17);
            if (xing_off + 8 < scan_limit) {
                if (std::memcmp(scan_buf.data() + xing_off, "Xing", 4) == 0 ||
                    std::memcmp(scan_buf.data() + xing_off, "Info", 4) == 0) {
                    meta.is_vbr = (std::memcmp(scan_buf.data() + xing_off, "Xing", 4) == 0);
                    // Check for LAME encoder string
                    if (xing_off + 150 < scan_limit) {
                        for (size_t l = xing_off; l + 8 < xing_off + 160; ++l) {
                            if (std::memcmp(scan_buf.data() + l, "LAME", 4) == 0) {
                                meta.encoder = std::string(reinterpret_cast<char*>(scan_buf.data() + l), 9);
                                break;
                            }
                        }
                    }
                }
            }
            break;
        }
    }
}

static void parse_flac(std::ifstream& file, AudioMetadata& meta) {
    uint8_t magic[4];
    file.seekg(0, std::ios::beg);
    if (!file.read(reinterpret_cast<char*>(magic), 4)) return;

    if (std::memcmp(magic, "fLaC", 4) == 0) {
        meta.format = "flac";
        meta.valid = true;
        meta.is_vbr = true;

        // Read STREAMINFO block (38 bytes)
        uint8_t block_hdr[4];
        if (file.read(reinterpret_cast<char*>(block_hdr), 4)) {
            uint8_t block_type = block_hdr[0] & 0x7F;
            if (block_type == 0) { // STREAMINFO
                uint8_t sinfo[34];
                if (file.read(reinterpret_cast<char*>(sinfo), 34)) {
                    meta.sample_rate = (sinfo[10] << 12) | (sinfo[11] << 4) | (sinfo[12] >> 4);
                    meta.channels = ((sinfo[12] >> 1) & 0x07) + 1;
                }
            }
        }
    }
}

static void parse_wav(std::ifstream& file, AudioMetadata& meta) {
    uint8_t riff[12];
    file.seekg(0, std::ios::beg);
    if (!file.read(reinterpret_cast<char*>(riff), 12)) return;

    if (std::memcmp(riff, "RIFF", 4) == 0 && std::memcmp(riff + 8, "WAVE", 4) == 0) {
        meta.format = "wav";
        meta.valid = true;

        // Search for fmt chunk
        uint8_t chunk_hdr[8];
        while (file.read(reinterpret_cast<char*>(chunk_hdr), 8)) {
            uint32_t chunk_len = chunk_hdr[4] | (chunk_hdr[5] << 8) | (chunk_hdr[6] << 16) | (chunk_hdr[7] << 24);
            if (std::memcmp(chunk_hdr, "fmt ", 4) == 0 && chunk_len >= 16) {
                uint8_t fmt_data[16];
                if (file.read(reinterpret_cast<char*>(fmt_data), 16)) {
                    meta.channels = fmt_data[2] | (fmt_data[3] << 8);
                    meta.sample_rate = fmt_data[4] | (fmt_data[5] << 8) | (fmt_data[6] << 16) | (fmt_data[7] << 24);
                    uint32_t byte_rate = fmt_data[8] | (fmt_data[9] << 8) | (fmt_data[10] << 16) | (fmt_data[11] << 24);
                    meta.bitrate_kbps = (byte_rate * 8) / 1000;
                }
                break;
            } else {
                file.seekg(chunk_len, std::ios::cur);
            }
        }
    }
}

static void escape_json(std::ostream& os, const std::string& s) {
    for (char c : s) {
        if (c == '"') os << "\\\"";
        else if (c == '\\') os << "\\\\";
        else if (c == '\n') os << "\\n";
        else if (c == '\r') os << "\\r";
        else if (c == '\t') os << "\\t";
        else if (static_cast<unsigned char>(c) >= 32) os << c;
    }
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: audio_probe <audio_filepath> [--json]\n";
        return 1;
    }

    std::string filepath = argv[1];
    bool json_mode = (argc >= 3 && std::string(argv[2]) == "--json");

    std::ifstream file(filepath, std::ios::binary);
    if (!file.is_open()) {
        if (json_mode) {
            std::cout << "{\"valid\": false, \"error\": \"Cannot open file\"}\n";
        } else {
            std::cerr << "[ERROR] Cannot open file: " << filepath << "\n";
        }
        return 1;
    }

    AudioMetadata meta;
    file.seekg(0, std::ios::end);
    meta.file_size_bytes = file.tellg();
    file.seekg(0, std::ios::beg);

    // Identify format
    parse_mp3_frames(file, meta);
    if (!meta.valid) {
        parse_flac(file, meta);
    }
    if (!meta.valid) {
        parse_wav(file, meta);
    }

    if (json_mode) {
        std::cout << "{\n";
        std::cout << "  \"valid\": " << (meta.valid ? "true" : "false") << ",\n";
        std::cout << "  \"format\": \"" << meta.format << "\",\n";
        std::cout << "  \"title\": \""; escape_json(std::cout, meta.title); std::cout << "\",\n";
        std::cout << "  \"artist\": \""; escape_json(std::cout, meta.artist); std::cout << "\",\n";
        std::cout << "  \"album\": \""; escape_json(std::cout, meta.album); std::cout << "\",\n";
        std::cout << "  \"year\": \"" << meta.year << "\",\n";
        std::cout << "  \"sample_rate\": " << meta.sample_rate << ",\n";
        std::cout << "  \"channels\": " << meta.channels << ",\n";
        std::cout << "  \"bitrate_kbps\": " << meta.bitrate_kbps << ",\n";
        std::cout << "  \"is_vbr\": " << (meta.is_vbr ? "true" : "false") << ",\n";
        std::cout << "  \"has_cover_art\": " << (meta.has_cover_art ? "true" : "false") << ",\n";
        std::cout << "  \"cover_mime\": \"" << meta.cover_mime << "\",\n";
        std::cout << "  \"file_size_bytes\": " << meta.file_size_bytes << ",\n";
        std::cout << "  \"encoder\": \"" << meta.encoder << "\"\n";
        std::cout << "}\n";
    } else {
        std::cout << "=================================================\n";
        std::cout << "       Audio Probe Utility (C++20 Native)        \n";
        std::cout << "=================================================\n";
        std::cout << "Format         : " << meta.format << "\n";
        std::cout << "Title          : " << (meta.title.empty() ? "-" : meta.title) << "\n";
        std::cout << "Artist         : " << (meta.artist.empty() ? "-" : meta.artist) << "\n";
        std::cout << "Album          : " << (meta.album.empty() ? "-" : meta.album) << "\n";
        std::cout << "Sample Rate    : " << meta.sample_rate << " Hz\n";
        std::cout << "Channels       : " << meta.channels << "\n";
        std::cout << "Bitrate        : " << meta.bitrate_kbps << " kbps" << (meta.is_vbr ? " (VBR)" : " (CBR)") << "\n";
        std::cout << "Cover Art      : " << (meta.has_cover_art ? "Yes" : "None") << "\n";
        std::cout << "Encoder        : " << (meta.encoder.empty() ? "-" : meta.encoder) << "\n";
        std::cout << "File Size      : " << std::fixed << std::setprecision(2)
                  << (meta.file_size_bytes / (1024.0 * 1024.0)) << " MB\n";
        std::cout << "=================================================\n";
    }

    return 0;
}
