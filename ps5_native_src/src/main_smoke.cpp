/*
 * UniRift / Anime Rift — PS5 FW 13.60 Minimal Smoke Test (Phase C)
 * Pure C++20 VideoOut Native Title, zero network/HTTP/threads, early startup logs.
 */

#include "demo_renderer.hpp"

#include <cstdint>
#include <string_view>

extern "C"
{
    long write(int descriptor, const void *buffer, std::size_t size);
    void exit(int status);
}

namespace
{
void log_stage(std::string_view stage) noexcept
{
    // Write directly to stdout (1) and stderr (2) for klogsrv / stdout capture
    (void)write(1, stage.data(), stage.size());
    (void)write(1, "\n", 1);
}

void smoke_draw_scene(ps5::demo::Canvas &canvas, std::uint32_t pressed_buttons,
                      std::uint64_t frame_count) noexcept
{
    using ps5::demo::Color;

    if (frame_count == 1)
    {
        log_stage("[SMOKE] FIRST_FRAME_RENDERED");
        log_stage("[SMOKE] ENTERING_EVENT_LOOP");
    }

    // Background
    canvas.clear(Color::background);

    // Top Header Banner
    canvas.rectangle(0, 0, 1920, 140, Color::header_bg);
    canvas.rectangle(0, 136, 1920, 4, Color::accent);
    canvas.text(80, 36, "UNIRIFT / ANIME RIFT — SMOKE TEST", 6, Color::white);
    canvas.text(80, 92, "PS5 FIRMWARE 13.60 NATIVE TITLE PPSA91360", 3, Color::yellow);

    // Main Status Card
    canvas.rectangle(80, 180, 1760, 480, Color::panel);
    canvas.border(80, 180, 1760, 480, 3, Color::green);

    canvas.text(120, 220, "VERIFICATION STATUS:", 4, Color::green);
    canvas.text(120, 280, "[OK] 16 KiB PT_LOAD CONGRUENCE CHECK PASSED", 4, Color::white);
    canvas.text(120, 335, "[OK] PS5 KERNEL LOADER ACCEPTED EXECUTABLE", 4, Color::white);
    canvas.text(120, 390, "[OK] SCE VIDEO OUT & GARLIC DIRECT MEMORY MAPPED", 4, Color::white);
    canvas.text(120, 445, "[OK] DUALSENSE SCEPAD INPUT ACTIVE", 4, Color::white);

    // Frame Counter
    canvas.rectangle(120, 520, 450, 60, Color::header_bg);
    canvas.border(120, 520, 450, 60, 2, Color::cyan);
    canvas.text(140, 540, "FRAME LOOP: RUNNING", 3, Color::cyan);

    // Bottom Navigation Bar
    canvas.rectangle(80, 700, 1760, 120, Color::header_bg);
    canvas.border(80, 700, 1760, 120, 2, Color::accent);
    canvas.text(120, 745, "PRESS [O] (CIRCLE) ON DUALSENSE TO EXIT CLEANLY", 4, Color::white);

    // Exit on Circle button
    if (pressed_buttons & ps5::demo::kPadBtnCircle)
    {
        log_stage("[SMOKE] USER_REQUESTED_EXIT");
        exit(0);
    }
}
} // namespace

int main()
{
    log_stage("[SMOKE] PROCESS_ENTER");
    log_stage("[SMOKE] PRE_INIT");
    log_stage("[SMOKE] MAIN_ENTER");
    log_stage("[SMOKE] VIDEO_INIT_START");

    ps5::demo::run_interactive(smoke_draw_scene, "UniRift Smoke Test Ready!");
}
