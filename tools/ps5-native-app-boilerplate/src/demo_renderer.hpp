/*
 * Anime Rift PS5 13.60 Native Edition - VideoOut & DualSense UI Engine
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#pragma once

#include <cstdint>
#include <span>
#include <string_view>

namespace ps5::demo
{
// ABGR8888 / RGBA8_SRGB colors for PS5 SceVideoOut
enum class Color : std::uint32_t
{
    background = UINT32_C(0xff140b08),
    header_bg  = UINT32_C(0xff24140e),
    panel      = UINT32_C(0xff2c1a12),
    panel_sel  = UINT32_C(0xff4a2b1d),
    accent     = UINT32_C(0xff3b5bff), // Vibrant orange-red/gold accent in RGBA
    white      = UINT32_C(0xffffffff),
    muted      = UINT32_C(0xffb8a89e),
    cyan       = UINT32_C(0xffffff00),
    magenta    = UINT32_C(0xffff00ff),
    yellow     = UINT32_C(0xff00d4ff),
    green      = UINT32_C(0xff40ff40),
};

// DualSense button bitmasks (ScePadButtonDataOffset)
constexpr std::uint32_t kPadBtnOptions  = 0x00000008U;
constexpr std::uint32_t kPadBtnUp       = 0x00000010U;
constexpr std::uint32_t kPadBtnRight    = 0x00000020U;
constexpr std::uint32_t kPadBtnDown     = 0x00000040U;
constexpr std::uint32_t kPadBtnLeft     = 0x00000080U;
constexpr std::uint32_t kPadBtnL1       = 0x00000400U;
constexpr std::uint32_t kPadBtnR1       = 0x00000800U;
constexpr std::uint32_t kPadBtnTriangle = 0x00001000U;
constexpr std::uint32_t kPadBtnCircle   = 0x00002000U;
constexpr std::uint32_t kPadBtnCross    = 0x00004000U;
constexpr std::uint32_t kPadBtnSquare   = 0x00008000U;

class Canvas;
[[noreturn]] void run_interactive(void (*update_and_draw)(Canvas &, std::uint32_t pressed_buttons,
                                                          std::uint64_t frame_count) noexcept,
                                  std::string_view ready_message) noexcept;

class Canvas final
{
  public:
    void clear(Color color) noexcept;
    void rectangle(unsigned x, unsigned y, unsigned width, unsigned height, Color color) noexcept;
    void border(unsigned x, unsigned y, unsigned width, unsigned height, unsigned thickness,
                Color color) noexcept;
    void circle(unsigned center_x, unsigned center_y, unsigned radius, Color color) noexcept;
    void triangle(unsigned center_x, unsigned top, unsigned half_width, unsigned height,
                  Color color) noexcept;
    void text(unsigned x, unsigned y, std::string_view value, unsigned scale, Color color) noexcept;

  private:
    explicit Canvas(std::uint32_t *pixels) noexcept : pixels_{pixels}
    {
    }

    std::uint32_t *pixels_;

    friend void run_interactive(void (*update_and_draw)(Canvas &, std::uint32_t pressed_buttons,
                                                        std::uint64_t frame_count) noexcept,
                                std::string_view ready_message) noexcept;
};

void notify(std::string_view message) noexcept;
void read_asset_text(const char *path, std::span<char> destination,
                     std::string_view fallback) noexcept;
} // namespace ps5::demo
