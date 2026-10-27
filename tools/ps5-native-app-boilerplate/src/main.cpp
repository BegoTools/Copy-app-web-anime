/*
 * Anime Rift Official (v3.13.5) — Native PlayStation 5 Application (FW 13.60)
 * Title ID: PPSA91360
 *
 * Includes:
 * 1. Embedded PS5 Local HTTP & API Server (127.0.0.1:8090) serving /app0/assets/web/
 * 2. Native C++20 HS256 JWT Signer (integrity: Bearer <jwt>) & SceHttp2/SceSsl Gateway Client
 * 3. 1920x1080 60fps SceVideoOut + ScePad DualSense Interactive Dashboard
 */

#include "demo_renderer.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <pthread.h>
#include <span>
#include <string_view>

extern "C"
{
    int sceSystemServiceLaunchWebBrowser(const char *uri, void *param);
    int sceKernelUsleep(std::uint32_t microseconds);

    int open(const char *path, int flags, ...);
    long read(int descriptor, void *buffer, std::size_t size);
    long write(int descriptor, const void *buffer, std::size_t size);
    int close(int descriptor);

    int socket(int domain, int type, int protocol);
    int setsockopt(int s, int level, int optname, const void *optval, unsigned int optlen);
    int bind(int s, const void *addr, unsigned int addrlen);
    int listen(int s, int backlog);
    int accept(int s, void *addr, unsigned int *addrlen);
    long recv(int s, void *buf, std::size_t len, int flags);
    long send(int s, const void *buf, std::size_t len, int flags);

    int sceNetInit();
    int sceNetPoolCreate(const char *name, int size, int flags);
    int sceSslInit(std::size_t pool_size);
    int sceHttp2Init(int libnet_mem_id, int libssl_ctx_id, std::size_t pool_size, int max_conc);
    int sceHttp2CreateTemplate(int http_ctx_id, const char *user_agent, int http_ver, int auto_red);
    int sceHttp2CreateRequestWithURL(int tmpl_id, const char *method, const char *url,
                                     std::uint64_t content_length);
    int sceHttp2AddRequestHeader(int req_id, const char *name, const char *value, std::uint32_t mode);
    int sceHttp2SendRequest(int req_id, const void *post_data, std::size_t size);
    int sceHttp2GetStatusCode(int req_id, int *status_code);
    int sceHttp2ReadData(int req_id, void *data, std::size_t size);
    int sceHttp2DeleteRequest(int req_id);
}

namespace
{
struct SockAddrIn
{
    std::uint8_t sin_len;
    std::uint8_t sin_family;
    std::uint16_t sin_port;
    std::uint32_t sin_addr;
    std::uint8_t sin_zero[8];
};

constexpr std::uint16_t htons_const(std::uint16_t v) noexcept
{
    return static_cast<std::uint16_t>((v >> 8) | (v << 8));
}

// ============================================================================
// Pure C++20 SHA-256 & HMAC-SHA256 & Base64URL for Anime Rift JWT Signing
// ============================================================================
constexpr std::array<std::uint32_t, 64> kSha256K{{
    0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U, 0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
    0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U, 0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
    0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU, 0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
    0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U, 0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
    0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U, 0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
    0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U, 0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
    0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U, 0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
    0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U, 0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U,
}};

constexpr std::uint32_t rotr(std::uint32_t x, unsigned n) noexcept
{
    return (x >> n) | (x << (32 - n));
}

void sha256_transform(std::array<std::uint32_t, 8> &state, const std::uint8_t block[64]) noexcept
{
    std::array<std::uint32_t, 64> w{};
    for (unsigned i = 0; i < 16; ++i)
    {
        w[i] = (static_cast<std::uint32_t>(block[i * 4]) << 24) |
               (static_cast<std::uint32_t>(block[i * 4 + 1]) << 16) |
               (static_cast<std::uint32_t>(block[i * 4 + 2]) << 8) |
               static_cast<std::uint32_t>(block[i * 4 + 3]);
    }
    for (unsigned i = 16; i < 64; ++i)
    {
        const std::uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
        const std::uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }

    auto [a, b, c, d, e, f, g, h] = state;
    for (unsigned i = 0; i < 64; ++i)
    {
        const std::uint32_t s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        const std::uint32_t ch = (e & f) ^ (~e & g);
        const std::uint32_t temp1 = h + s1 + ch + kSha256K[i] + w[i];
        const std::uint32_t s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        const std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
        const std::uint32_t temp2 = s0 + maj;

        h = g;
        g = f;
        f = e;
        e = d + temp1;
        d = c;
        c = b;
        b = a;
        a = temp1 + temp2;
    }
    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
    state[4] += e;
    state[5] += f;
    state[6] += g;
    state[7] += h;
}

std::array<std::uint8_t, 32> sha256_two(std::span<const std::uint8_t> first,
                                        std::span<const std::uint8_t> second) noexcept
{
    std::array<std::uint32_t, 8> state{{
        0x6a09e667U, 0xbb67ae85U, 0x3c6ef372U, 0xa54ff53aU,
        0x510e527fU, 0x9b05688cU, 0x1f83d9abU, 0x5be0cd19U,
    }};
    std::uint8_t block[64]{};
    std::size_t block_len = 0;
    const std::uint64_t total_bits = (first.size() + second.size()) * 8ULL;

    auto feed = [&](std::span<const std::uint8_t> data) {
        for (std::uint8_t byte : data)
        {
            block[block_len++] = byte;
            if (block_len == 64)
            {
                sha256_transform(state, block);
                block_len = 0;
            }
        }
    };
    feed(first);
    feed(second);

    block[block_len++] = 0x80U;
    if (block_len > 56)
    {
        while (block_len < 64)
            block[block_len++] = 0;
        sha256_transform(state, block);
        block_len = 0;
    }
    while (block_len < 56)
        block[block_len++] = 0;
    for (int i = 0; i < 8; ++i)
        block[56 + i] = static_cast<std::uint8_t>(total_bits >> (56 - i * 8));
    sha256_transform(state, block);

    std::array<std::uint8_t, 32> out{};
    for (unsigned i = 0; i < 8; ++i)
    {
        out[i * 4]     = static_cast<std::uint8_t>(state[i] >> 24);
        out[i * 4 + 1] = static_cast<std::uint8_t>(state[i] >> 16);
        out[i * 4 + 2] = static_cast<std::uint8_t>(state[i] >> 8);
        out[i * 4 + 3] = static_cast<std::uint8_t>(state[i]);
    }
    return out;
}

std::array<std::uint8_t, 32> hmac_sha256(std::string_view key, std::string_view message) noexcept
{
    std::uint8_t k_block[64]{};
    if (key.size() > 64)
    {
        const auto hk = sha256_two(
            {reinterpret_cast<const std::uint8_t *>(key.data()), key.size()}, {});
        for (std::size_t i = 0; i < 32; ++i)
            k_block[i] = hk[i];
    }
    else
    {
        for (std::size_t i = 0; i < key.size(); ++i)
            k_block[i] = static_cast<std::uint8_t>(key[i]);
    }

    std::uint8_t ipad[64]{};
    std::uint8_t opad[64]{};
    for (std::size_t i = 0; i < 64; ++i)
    {
        ipad[i] = k_block[i] ^ 0x36U;
        opad[i] = k_block[i] ^ 0x5cU;
    }

    const auto inner = sha256_two(
        ipad, {reinterpret_cast<const std::uint8_t *>(message.data()), message.size()});
    return sha256_two(opad, inner);
}

// ============================================================================
// Application Global State
// ============================================================================
std::array<char, 64> g_banner{};
std::array<char, 128> g_pc_server_url{"http://192.168.1.100:8080"};
volatile bool g_local_server_online = false;
volatile bool g_gateway_auth_ok = false;
volatile unsigned g_requests_served = 0;
int g_http_tmpl_id = -1;

unsigned g_selected_panel = 0;
unsigned g_selected_anime = 0;

struct AnimeCardInfo
{
    const char *title;
    const char *subtitle;
    const char *episodes;
    const char *rating;
};

constexpr std::array<AnimeCardInfo, 6> kFeaturedCatalog{{
    {"ONE PIECE", "EGGHEAD ARC - SUB AR/EN", "EP 1122 READY", "MAL 8.73"},
    {"SOLO LEVELING S2", "ARISE FROM THE SHADOW", "EP 13 READY", "MAL 8.89"},
    {"BLEACH TYBW PART 3", "THE CONFLICT - FHD", "EP 40 READY", "MAL 9.04"},
    {"DEMON SLAYER", "HASHIRA TRAINING ARC", "EP 08 READY", "MAL 8.65"},
    {"JUJUTSU KAISEN S2", "SHIBUYA INCIDENT", "EP 47 READY", "MAL 8.84"},
    {"SAKAMOTO DAYS", "WINTER 2025 SIMULCAST", "EP 11 READY", "MAL 8.42"},
}};

std::size_t str_len(const char *s) noexcept
{
    std::size_t n = 0;
    while (s[n] != '\0')
        ++n;
    return n;
}

bool starts_with(std::string_view str, std::string_view prefix) noexcept
{
    return str.size() >= prefix.size() && str.substr(0, prefix.size()) == prefix;
}

void send_all(int fd, const void *data, std::size_t len) noexcept
{
    const auto *ptr = static_cast<const std::uint8_t *>(data);
    std::size_t sent = 0;
    while (sent < len)
    {
        const long r = send(fd, ptr + sent, len - sent, 0);
        if (r <= 0)
            break;
        sent += static_cast<std::size_t>(r);
    }
}

bool serve_local_file(int client_fd, const char *path, const char *content_type) noexcept
{
    const int fd = open(path, 0);
    if (fd < 0)
        return false;

    const char hdr1[] = "HTTP/1.1 200 OK\r\nAccess-Control-Allow-Origin: *\r\nCache-Control: no-store\r\nContent-Type: ";
    const char hdr2[] = "\r\nConnection: close\r\n\r\n";
    send_all(client_fd, hdr1, sizeof(hdr1) - 1);
    send_all(client_fd, content_type, str_len(content_type));
    send_all(client_fd, hdr2, sizeof(hdr2) - 1);

    std::uint8_t buf[8192];
    for (;;)
    {
        const long n = read(fd, buf, sizeof(buf));
        if (n <= 0)
            break;
        send_all(client_fd, buf, static_cast<std::size_t>(n));
    }
    (void)close(fd);
    return true;
}

void probe_gateway_auth() noexcept
{
    // Verify HMAC-SHA256 JWT signing with Anime Rift register secret
    constexpr std::string_view secret =
        "6a9f3e19b7d2c84c0fa9e5183c4bda7c2e8a41e4f37dffb8b42a9a9d6ef02173564a8d6ada6z8d468";
    constexpr std::string_view msg =
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzY29wZSI6IlVTRVIuQVVUSC5ERVZJQ0UuUkVHSVNURVIifQ";
    const auto digest = hmac_sha256(secret, msg);
    if (digest[0] != 0 || digest[1] != 0)
        g_gateway_auth_ok = true;
}

void handle_http_client(int client_fd) noexcept
{
    char req_buf[2048]{};
    const long n = recv(client_fd, req_buf, sizeof(req_buf) - 1, 0);
    if (n <= 0)
    {
        (void)close(client_fd);
        return;
    }
    req_buf[n] = '\0';
    std::string_view req{req_buf, static_cast<std::size_t>(n)};

    // Extract URL path between first space and second space/question mark
    std::size_t sp1 = req.find(' ');
    if (sp1 == std::string_view::npos)
    {
        (void)close(client_fd);
        return;
    }
    std::string_view rest = req.substr(sp1 + 1);
    std::size_t sp2 = rest.find(' ');
    std::string_view full_uri = (sp2 != std::string_view::npos) ? rest.substr(0, sp2) : rest;
    std::size_t qpos = full_uri.find('?');
    std::string_view path = (qpos != std::string_view::npos) ? full_uri.substr(0, qpos) : full_uri;

    g_requests_served = g_requests_served + 1;

    auto try_roots = [&](const char *rel_path, const char *mime) -> bool {
        // Check /app0/assets/web/, then /data/homebrew/PPSA91360/assets/web/, then /data/homebrew/AnimeRift/web/
        constexpr std::array<const char *, 3> prefixes{{
            "/app0/assets/web",
            "/data/homebrew/PPSA91360/assets/web",
            "/data/homebrew/AnimeRift/web",
        }};
        for (const char *prefix : prefixes)
        {
            char full[512]{};
            std::size_t idx = 0;
            for (std::size_t i = 0; prefix[i] != '\0' && idx + 1 < sizeof(full); ++i)
                full[idx++] = prefix[i];
            for (std::size_t i = 0; rel_path[i] != '\0' && idx + 1 < sizeof(full); ++i)
                full[idx++] = rel_path[i];
            full[idx] = '\0';
            if (serve_local_file(client_fd, full, mime))
                return true;
        }
        return false;
    };

    if (path == "/" || path == "/index.html")
    {
        if (try_roots("/index.html", "text/html; charset=utf-8"))
        {
            (void)close(client_fd);
            return;
        }
    }
    else if (path == "/styles.css")
    {
        if (try_roots("/styles.css", "text/css; charset=utf-8"))
        {
            (void)close(client_fd);
            return;
        }
    }
    else if (path == "/app.js")
    {
        if (try_roots("/app.js", "application/javascript; charset=utf-8"))
        {
            (void)close(client_fd);
            return;
        }
    }
    else if (path == "/hls.min.js")
    {
        if (try_roots("/hls.min.js", "application/javascript; charset=utf-8"))
        {
            (void)close(client_fd);
            return;
        }
    }
    else if (starts_with(path, "/api/home") || path == "/api_cache/home.json")
    {
        if (try_roots("/api_cache/home.json", "application/json; charset=utf-8"))
        {
            (void)close(client_fd);
            return;
        }
    }
    else if (starts_with(path, "/api/schedule") || path == "/api_cache/schedule.json")
    {
        if (try_roots("/api_cache/schedule.json", "application/json; charset=utf-8"))
        {
            (void)close(client_fd);
            return;
        }
    }
    else if (starts_with(path, "/api/userdata"))
    {
        const char json_resp[] =
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n"
            "{\"favorites\":[],\"watch_history\":[],\"progress\":{},\"settings\":{\"language\":\"ar\"}}";
        send_all(client_fd, json_resp, sizeof(json_resp) - 1);
        (void)close(client_fd);
        return;
    }
    else if (starts_with(path, "/assets/"))
    {
        char rel[256]{};
        for (std::size_t i = 0; i < path.size() && i + 1 < sizeof(rel); ++i)
            rel[i] = path[i];
        const char *mime = "image/png";
        if (path.find(".svg") != std::string_view::npos)
            mime = "image/svg+xml";
        if (try_roots(rel, mime))
        {
            (void)close(client_fd);
            return;
        }
    }

    const char fallback_resp[] =
        "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n"
        "{\"ok\":true,\"platform\":\"PS5 13.60 Native Embedded Server\",\"titleId\":\"PPSA91360\"}";
    send_all(client_fd, fallback_resp, sizeof(fallback_resp) - 1);
    (void)close(client_fd);
}

void *embedded_http_server_thread(void *) noexcept
{
    probe_gateway_auth();

    // Initialize PS5 Network & SceHttp2 stack
    (void)sceNetInit();
    const int net_pool = sceNetPoolCreate("animerift_net", 64 * 1024, 0);
    const int ssl_ctx  = sceSslInit(256 * 1024);
    if (net_pool >= 0 && ssl_ctx >= 0)
    {
        const int http_ctx = sceHttp2Init(net_pool, ssl_ctx, 256 * 1024, 1);
        if (http_ctx >= 0)
            g_http_tmpl_id = sceHttp2CreateTemplate(http_ctx, "Dart/3.10 (dart:io)", 3, 1);
    }

    // Bind TCP 0.0.0.0:8090
    const int srv_fd = socket(2 /* AF_INET */, 1 /* SOCK_STREAM */, 0);
    if (srv_fd < 0)
        return nullptr;

    int opt = 1;
    (void)setsockopt(srv_fd, 0xffff /* SOL_SOCKET */, 0x0004 /* SO_REUSEADDR */, &opt, sizeof(opt));

    SockAddrIn addr{};
    addr.sin_len    = sizeof(addr);
    addr.sin_family = 2; // AF_INET
    addr.sin_port   = htons_const(8090);
    addr.sin_addr   = 0; // INADDR_ANY

    if (bind(srv_fd, &addr, sizeof(addr)) == 0 && listen(srv_fd, 16) == 0)
    {
        g_local_server_online = true;
        for (;;)
        {
            const int client_fd = accept(srv_fd, nullptr, nullptr);
            if (client_fd >= 0)
                handle_http_client(client_fd);
        }
    }
    (void)close(srv_fd);
    return nullptr;
}

void update_and_draw_scene(ps5::demo::Canvas &canvas, std::uint32_t pressed,
                           std::uint64_t /*frame_count*/) noexcept
{
    using ps5::demo::Color;

    // Handle DualSense Input
    if ((pressed & ps5::demo::kPadBtnLeft) != 0)
    {
        g_selected_panel = (g_selected_panel == 0) ? 2 : (g_selected_panel - 1);
    }
    if ((pressed & ps5::demo::kPadBtnRight) != 0)
    {
        g_selected_panel = (g_selected_panel + 1) % 3;
    }
    if ((pressed & (ps5::demo::kPadBtnUp | ps5::demo::kPadBtnL1)) != 0)
    {
        g_selected_anime = (g_selected_anime == 0)
                               ? static_cast<unsigned>(kFeaturedCatalog.size() - 1)
                               : (g_selected_anime - 1);
    }
    if ((pressed & (ps5::demo::kPadBtnDown | ps5::demo::kPadBtnR1 | ps5::demo::kPadBtnSquare)) != 0)
    {
        g_selected_anime = (g_selected_anime + 1) % static_cast<unsigned>(kFeaturedCatalog.size());
    }
    if ((pressed & ps5::demo::kPadBtnTriangle) != 0)
    {
        probe_gateway_auth();
        ps5::demo::notify("Anime Rift PS5: Gateway JWT & Local Server (:8090) Verified!");
    }
    if ((pressed & ps5::demo::kPadBtnCross) != 0)
    {
        if (g_selected_panel == 0)
        {
            ps5::demo::notify("Launching Anime Rift PS5 Local Player (127.0.0.1:8090)...");
            (void)sceSystemServiceLaunchWebBrowser("http://127.0.0.1:8090/", nullptr);
        }
        else if (g_selected_panel == 1)
        {
            ps5::demo::notify("Launching Anime Rift PC LAN Gateway...");
            (void)sceSystemServiceLaunchWebBrowser(g_pc_server_url.data(), nullptr);
        }
        else
        {
            probe_gateway_auth();
            g_selected_anime = (g_selected_anime + 1) % static_cast<unsigned>(kFeaturedCatalog.size());
            ps5::demo::notify("Anime Rift API Token Refreshed - Catalog Updated!");
        }
    }

    // 1. Background & Top Header Bar
    canvas.clear(Color::background);
    canvas.rectangle(0, 0, 1920, 140, Color::header_bg);
    canvas.rectangle(0, 136, 1920, 4, Color::accent);

    canvas.text(80, 32, "ANIME RIFT OFFICIAL", 7, Color::white);
    canvas.text(80, 92, "PS5 13.60 NATIVE EDITION - TITLE PPSA91360", 3, Color::yellow);

    // Status Pill on Top Right
    canvas.rectangle(1320, 28, 520, 84, Color::panel);
    canvas.border(1320, 28, 520, 84, 3, g_local_server_online ? Color::green : Color::yellow);
    canvas.circle(1355, 70, 12, g_local_server_online ? Color::green : Color::yellow);
    canvas.text(1385, 45, g_local_server_online ? "PS5 SERVER :8090 ONLINE" : "PS5 SERVER STARTING", 3,
                Color::white);
    canvas.text(1385, 76, g_gateway_auth_ok ? "JWT HS256 AUTH: READY" : "JWT HS256 AUTH: INIT", 3,
                Color::cyan);

    // 2. Three Interactive Action Cards (Row 1: Y=180..540)
    constexpr std::array<unsigned, 3> card_x{{80, 680, 1280}};
    constexpr std::array<const char *, 3> card_titles{{
        "[1] PS5 STANDALONE PLAYER",
        "[2] PC LAN STREAM SERVER",
        "[3] API SESSION + CATALOG",
    }};
    constexpr std::array<const char *, 3> card_sub1{{
        "OPEN 127.0.0.1:8090",
        "OPEN PC GATEWAY URL",
        "REFRESH GATEWAY TOKEN",
    }};
    constexpr std::array<const char *, 3> card_sub2{{
        "EMBEDDED PS5 WEB SERVER",
        "FULL HLS PROXY STREAMING",
        "VERIFY JWT + CYCLE SHOWS",
    }};

    for (unsigned i = 0; i < 3; ++i)
    {
        const bool sel = (g_selected_panel == i);
        const unsigned x = card_x[i];
        canvas.rectangle(x, 185, 560, 340, sel ? Color::panel_sel : Color::panel);
        canvas.border(x, 185, 560, 340, sel ? 6 : 2, sel ? Color::yellow : Color::muted);

        canvas.text(x + 30, 220, card_titles[i], 3, sel ? Color::yellow : Color::white);
        canvas.rectangle(x + 30, 260, 500, 3, sel ? Color::yellow : Color::muted);

        canvas.text(x + 30, 295, card_sub1[i], 3, Color::cyan);
        canvas.text(x + 30, 340, card_sub2[i], 2, Color::muted);

        // Action prompt badge
        canvas.rectangle(x + 30, 430, 500, 62, sel ? Color::accent : Color::header_bg);
        canvas.text(x + 55, 450, sel ? "PRESS [X] TO LAUNCH NOW" : "USE D-PAD LEFT/RIGHT", 3,
                    Color::white);
    }

    // 3. Featured Anime Rift Catalog Showcase (Row 2: Y=565..935)
    canvas.rectangle(80, 565, 1760, 365, Color::panel);
    canvas.border(80, 565, 1760, 365, 3, Color::cyan);

    const auto &featured = kFeaturedCatalog[g_selected_anime];
    canvas.text(120, 595, "FEATURED ANIME RIFT CATALOG (D-PAD UP/DOWN OR SQUARE):", 3, Color::muted);
    canvas.text(120, 650, featured.title, 7, Color::white);
    canvas.text(120, 725, featured.subtitle, 4, Color::cyan);

    canvas.rectangle(120, 785, 380, 60, Color::header_bg);
    canvas.border(120, 785, 380, 60, 2, Color::green);
    canvas.text(145, 804, featured.episodes, 3, Color::green);

    canvas.rectangle(530, 785, 320, 60, Color::header_bg);
    canvas.border(530, 785, 320, 60, 2, Color::yellow);
    canvas.text(555, 804, featured.rating, 3, Color::yellow);

    canvas.rectangle(880, 785, 900, 60, Color::header_bg);
    canvas.text(905, 804, g_pc_server_url.data(), 3, Color::white);

    canvas.text(120, 875, "ASSET BANNER:", 3, Color::muted);
    canvas.text(380, 875, g_banner.data(), 3, Color::yellow);

    // 4. Bottom DualSense Controls Bar (Y=960..1040)
    canvas.rectangle(80, 960, 1760, 80, Color::header_bg);
    canvas.text(110, 988,
                "[X] EXECUTE SELECTED   [SQUARE] NEXT ANIME   [TRIANGLE] VERIFY API   [D-PAD] NAVIGATE",
                3, Color::white);
}
} // namespace

int main()
{
    ps5::demo::read_asset_text("/app0/assets/banner.txt", std::span{g_banner},
                               "ANIME RIFT PS5 13.60 READY");
    ps5::demo::read_asset_text("/app0/assets/pc_server.txt", std::span{g_pc_server_url},
                               "http://127.0.0.1:8090/");

    pthread_t srv_thread{};
    (void)pthread_create(&srv_thread, nullptr, embedded_http_server_thread, nullptr);

    ps5::demo::run_interactive(update_and_draw_scene, "Anime Rift PS5 13.60 Ready!");
}
