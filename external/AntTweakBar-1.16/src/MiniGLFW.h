//  ---------------------------------------------------------------------------
//
//  @file       MiniGLFW.h
//  @brief      A subset of GLFW definitions needed to compile helper functions
//              implemented in TwEventGLFW.c
//
//  notes:    - Private header
//            - AntTweakBar.dll does not need to link with GLFW, 
//              it just needs some definitions for its helper functions.
//            - This header is provided to avoid the need of having GLFW
//              installed to recompile AntTweakBar.
//            - The key and modifier values below are the GLFW 3 numbering
//              (glfw3.h), which differs from GLFW 2. Do not use this header in
//              your own programs, use the glfw3.h header from the actual GLFW
//              library instead: http://www.glfw.org
//
//  ---------------------------------------------------------------------------

#if !defined MINI_GLFW_INCLUDED
#define MINI_GLFW_INCLUDED

#ifdef __cplusplus
extern "C" {
#endif

// Key and button state/action definitions
#define GLFW_RELEASE          0
#define GLFW_PRESS            1
#define GLFW_REPEAT           2

// Modifier key flags (reported by GLFW 3 with key and mouse button events)
#define GLFW_MOD_SHIFT        0x0001
#define GLFW_MOD_CONTROL      0x0002
#define GLFW_MOD_ALT          0x0004
#define GLFW_MOD_SUPER        0x0008

// Keyboard key definitions (GLFW 3 numbering)
#define GLFW_KEY_UNKNOWN      -1
#define GLFW_KEY_SPACE        32
#define GLFW_KEY_SPECIAL      256 // internal: first non-printable key code
#define GLFW_KEY_ESCAPE       256
#define GLFW_KEY_ENTER        257
#define GLFW_KEY_TAB          258
#define GLFW_KEY_BACKSPACE    259
#define GLFW_KEY_INSERT       260
#define GLFW_KEY_DELETE       261
#define GLFW_KEY_RIGHT        262
#define GLFW_KEY_LEFT         263
#define GLFW_KEY_DOWN         264
#define GLFW_KEY_UP           265
#define GLFW_KEY_PAGE_UP      266
#define GLFW_KEY_PAGE_DOWN    267
#define GLFW_KEY_HOME         268
#define GLFW_KEY_END          269
#define GLFW_KEY_F1           290
#define GLFW_KEY_F2           291
#define GLFW_KEY_F3           292
#define GLFW_KEY_F4           293
#define GLFW_KEY_F5           294
#define GLFW_KEY_F6           295
#define GLFW_KEY_F7           296
#define GLFW_KEY_F8           297
#define GLFW_KEY_F9           298
#define GLFW_KEY_F10          299
#define GLFW_KEY_F11          300
#define GLFW_KEY_F12          301
#define GLFW_KEY_F13          302
#define GLFW_KEY_F14          303
#define GLFW_KEY_F15          304
#define GLFW_KEY_KP_0         320
#define GLFW_KEY_KP_1         321
#define GLFW_KEY_KP_2         322
#define GLFW_KEY_KP_3         323
#define GLFW_KEY_KP_4         324
#define GLFW_KEY_KP_5         325
#define GLFW_KEY_KP_6         326
#define GLFW_KEY_KP_7         327
#define GLFW_KEY_KP_8         328
#define GLFW_KEY_KP_9         329
#define GLFW_KEY_KP_DECIMAL   330
#define GLFW_KEY_KP_DIVIDE    331
#define GLFW_KEY_KP_MULTIPLY  332
#define GLFW_KEY_KP_SUBTRACT  333
#define GLFW_KEY_KP_ADD       334
#define GLFW_KEY_KP_ENTER     335
#define GLFW_KEY_KP_EQUAL     336
#define GLFW_KEY_LEFT_SHIFT   340
#define GLFW_KEY_LEFT_CONTROL 341
#define GLFW_KEY_LEFT_ALT     342
#define GLFW_KEY_RIGHT_SHIFT  344
#define GLFW_KEY_RIGHT_CONTROL 345
#define GLFW_KEY_RIGHT_ALT    346

// Mouse button
#define GLFW_MOUSE_BUTTON_LEFT   0
#define GLFW_MOUSE_BUTTON_RIGHT  1
#define GLFW_MOUSE_BUTTON_MIDDLE 2


#ifdef __cplusplus
}
#endif

#endif // !defined MINI_GLFW_INCLUDED

