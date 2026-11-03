#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

// Case-insensitive substring search
static const char* stristr(const char* haystack, const char* needle) {
    if (!haystack || !needle) return NULL;
    size_t needle_len = strlen(needle);
    if (needle_len == 0) return haystack;

    while (*haystack) {
        size_t i;
        for (i = 0; i < needle_len; i++) {
            char h = (char)tolower((unsigned char)haystack[i]);
            char n = (char)tolower((unsigned char)needle[i]);
            if (h != n) break;
        }
        if (i == needle_len) return haystack;
        haystack++;
    }
    return NULL;
}

// In-place string trimmer
static void trim_string(char* str) {
    if (!str) return;
    char* start = str;
    while (*start && (isspace((unsigned char)*start) || *start == '"' || *start == '\'')) {
        start++;
    }
    if (start != str) {
        memmove(str, start, strlen(start) + 1);
    }
    size_t len = strlen(str);
    while (len > 0) {
        char c = str[len - 1];
        if (isspace((unsigned char)c) || c == '"' || c == '\'') {
            str[len - 1] = '\0';
            len--;
        } else {
            break;
        }
    }
}

// Removes bracketed tags containing common video/audio clutter words
static void remove_bracket_tags(char* str) {
    const char* blacklist[] = {
        "official", "video", "audio", "lyric", "lirik",
        "remaster", "visualizer", "4k", "hd", "hq", "mv", "pv", "live", "clip",
        NULL
    };

    char* p = str;
    while (*p) {
        if (*p == '(' || *p == '[') {
            char close_char = (*p == '(') ? ')' : ']';
            char* close_pos = strchr(p, close_char);
            if (close_pos) {
                int should_remove = 0;
                for (int i = 0; blacklist[i] != NULL; i++) {
                    const char* found = stristr(p, blacklist[i]);
                    if (found && found < close_pos) {
                        should_remove = 1;
                        break;
                    }
                }
                if (should_remove) {
                    memmove(p, close_pos + 1, strlen(close_pos + 1) + 1);
                    continue;
                }
            }
        }
        p++;
    }
}

// Substring removal
static void remove_exact_substr(char* str, const char* needle) {
    size_t n_len = strlen(needle);
    char* p;
    while ((p = (char*)stristr(str, needle)) != NULL) {
        memmove(p, p + n_len, strlen(p + n_len) + 1);
    }
}

/**
 * Native C Title Cleaner & Metadata Sanitizer
 */
EXPORT int clean_title_native(
    const char* raw_title,
    const char* uploader,
    char* out_artist,
    char* out_title,
    int max_len
) {
    if (!raw_title || !out_artist || !out_title || max_len <= 0) {
        return -1;
    }

    char buffer[2048];
    strncpy(buffer, raw_title, sizeof(buffer) - 1);
    buffer[sizeof(buffer) - 1] = '\0';

    // 1. Remove bracketed clutter
    remove_bracket_tags(buffer);

    // 2. Remove trailing pipe and channel branding
    char* pipe = strchr(buffer, '|');
    if (pipe) {
        *pipe = '\0';
    }

    trim_string(buffer);

    // 3. Split Artist and Track Title
    const char* separators[] = { " - ", " – ", " — ", " : ", NULL };
    const char* found_sep = NULL;
    char* sep_pos = NULL;

    for (int i = 0; separators[i] != NULL; i++) {
        sep_pos = strstr(buffer, separators[i]);
        if (sep_pos) {
            found_sep = separators[i];
            break;
        }
    }

    char parsed_artist[1024] = {0};
    char parsed_title[1024] = {0};

    if (sep_pos && found_sep) {
        size_t artist_len = sep_pos - buffer;
        if (artist_len >= sizeof(parsed_artist)) artist_len = sizeof(parsed_artist) - 1;
        strncpy(parsed_artist, buffer, artist_len);
        parsed_artist[artist_len] = '\0';

        const char* title_start = sep_pos + strlen(found_sep);
        strncpy(parsed_title, title_start, sizeof(parsed_title) - 1);
        parsed_title[sizeof(parsed_title) - 1] = '\0';
    } else {
        if (uploader && strlen(uploader) > 0) {
            strncpy(parsed_artist, uploader, sizeof(parsed_artist) - 1);
        } else {
            strncpy(parsed_artist, "Unknown Artist", sizeof(parsed_artist) - 1);
        }
        strncpy(parsed_title, buffer, sizeof(parsed_title) - 1);
    }

    // Clean artist suffixes
    remove_exact_substr(parsed_artist, "VEVO");
    remove_exact_substr(parsed_artist, "- Topic");
    remove_exact_substr(parsed_artist, "Official Channel");

    trim_string(parsed_artist);
    trim_string(parsed_title);

    strncpy(out_artist, parsed_artist, max_len - 1);
    out_artist[max_len - 1] = '\0';

    strncpy(out_title, parsed_title, max_len - 1);
    out_title[max_len - 1] = '\0';

    return 0;
}

/**
 * Fast Binary Header Inspector
 */
EXPORT int verify_audio_header(const char* filepath) {
    if (!filepath) return 0;

    FILE* fp = fopen(filepath, "rb");
    if (!fp) return 0;

    unsigned char buf[16] = {0};
    size_t read_bytes = fread(buf, 1, 16, fp);
    fclose(fp);

    if (read_bytes < 4) return 0;

    if (buf[0] == 0x49 && buf[1] == 0x44 && buf[2] == 0x33) return 1; // ID3
    if (buf[0] == 0xFF && (buf[1] & 0xE0) == 0xE0) return 1;          // MP3 Frame
    if (buf[0] == 0x4F && buf[1] == 0x67 && buf[2] == 0x67 && buf[3] == 0x53) return 2; // OggS
    if (buf[0] == 0x66 && buf[1] == 0x4C && buf[2] == 0x61 && buf[3] == 0x43) return 4; // fLaC
    if (buf[0] == 0x52 && buf[1] == 0x49 && buf[2] == 0x46 && buf[3] == 0x46) {
        if (read_bytes >= 12 && buf[8] == 0x57 && buf[9] == 0x41 && buf[10] == 0x56 && buf[11] == 0x45) {
            return 5; // WAV
        }
    }
    if (read_bytes >= 8 && buf[4] == 0x66 && buf[5] == 0x74 && buf[6] == 0x79 && buf[7] == 0x70) {
        return 3; // M4A
    }

    return 0;
}

/**
 * Windows-Safe Filename Sanitizer
 */
EXPORT int sanitize_filename_native(const char* filename, char* out_clean, int max_len) {
    if (!filename || !out_clean || max_len <= 0) return -1;

    int out_idx = 0;
    for (int i = 0; filename[i] != '\0' && out_idx < max_len - 1; i++) {
        unsigned char c = (unsigned char)filename[i];
        if (c < 32) continue;
        if (c == '\\' || c == '/' || c == ':' || c == '*' || c == '?' ||
            c == '"' || c == '<' || c == '>' || c == '|') {
            continue;
        }
        out_clean[out_idx++] = (char)c;
    }
    out_clean[out_idx] = '\0';
    trim_string(out_clean);
    return 0;
}

static double goertzel_block_power(const short* samples, int num_samples, int sample_rate, double f_target, int block_size) {
    int num_blocks = num_samples / block_size;
    if (num_blocks <= 0) return 0.0;

    double omega = 2.0 * M_PI * f_target / (double)sample_rate;
    double coeff = 2.0 * cos(omega);
    double total_power = 0.0;

    for (int b = 0; b < num_blocks; b++) {
        const short* block = &samples[b * block_size];
        double s_prev = 0.0, s_prev2 = 0.0;
        for (int i = 0; i < block_size; i++) {
            double s = (double)block[i] + coeff * s_prev - s_prev2;
            s_prev2 = s_prev;
            s_prev = s;
        }
        double p = s_prev2 * s_prev2 + s_prev * s_prev - coeff * s_prev * s_prev2;
        total_power += p / (double)(block_size * block_size);
    }

    return total_power / (double)num_blocks;
}

/**
 * Native Audio Frequency Cutoff Analyzer (Goertzel Filter)
 * Evaluates frequency shelves from 14.0 kHz up to 22.0 kHz.
 * Returns the detected upper cutoff frequency in Hz (e.g. 16000, 18500, 20500, 22000).
 */
EXPORT int analyze_frequency_cutoff_native(const short* samples, int num_samples, int sample_rate) {
    if (!samples || num_samples < 2048 || sample_rate <= 0) {
        return 0;
    }

    int block_size = 2048;
    if (num_samples >= 4096) block_size = 4096;

    // 1. Reference power in musical mid-band (2 kHz - 7 kHz)
    double ref_power = 0.0;
    double mid_test[] = { 2000.0, 3500.0, 5000.0, 7000.0 };
    for (int i = 0; i < 4; i++) {
        double p = goertzel_block_power(samples, num_samples, sample_rate, mid_test[i], block_size);
        if (p > ref_power) ref_power = p;
    }

    if (ref_power <= 0.001) {
        return 0; // Silent audio
    }

    // Threshold: -50 dB relative to reference
    double threshold = ref_power * 0.00001;

    // 2. Scan from Nyquist down to 14.0 kHz in 500 Hz steps
    int max_test_hz = (sample_rate / 2) - 500;
    if (max_test_hz > 22000) max_test_hz = 22000;

    int detected_cutoff = 14000;
    for (int freq = max_test_hz; freq >= 14000; freq -= 500) {
        double p = goertzel_block_power(samples, num_samples, sample_rate, (double)freq, block_size);
        if (p > threshold) {
            detected_cutoff = freq;
            break;
        }
    }

    return detected_cutoff;
}
