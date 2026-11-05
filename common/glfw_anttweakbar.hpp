#ifndef GLFW_ANTTWEAKBAR_HPP
#define GLFW_ANTTWEAKBAR_HPP

// Bridge between GLFW 3 and AntTweakBar 1.16.
//
// - The TwEvent*GLFW helpers have GLFW3-compatible signatures, but they
//   return int while GLFW 3 callbacks return void, so they are called from
//   void trampolines instead of being cast to callback types.
// - TwWindowSize expects coordinates in framebuffer pixels, whereas GLFW 3
//   reports cursor positions in screen coordinates; the two differ on HiDPI
//   displays (eg. retina), so cursor events are scaled by the framebuffer /
//   window size ratio captured at initialization.
// - The return value of TwInit/TwDraw should not be ignored: on failure
//   AntTweakBar silently disables itself.

#include <stdio.h>
#include <GLFW/glfw3.h>
#include <AntTweakBar.h>

namespace {

double g_ATBScaleX = 1.0;
double g_ATBScaleY = 1.0;
bool g_ATBMouseOverBar = false;

}

static void TW_GLFW3_MouseButton(GLFWwindow *w, int button, int action, int mods)
{
    if( TwEventMouseButtonGLFW(w, button, action, mods) )
        g_ATBMouseOverBar = true;
}

static void TW_GLFW3_CursorPos(GLFWwindow *w, double x, double y)
{
    // TwEventMousePosGLFW returns whether an AntTweakBar element was hovered
    if( TwEventMousePosGLFW(w, x*g_ATBScaleX, y*g_ATBScaleY) )
        g_ATBMouseOverBar = true;
    else
        g_ATBMouseOverBar = false;
}

static void TW_GLFW3_Scroll(GLFWwindow *w, double xoffset, double yoffset)
{
    TwEventMouseWheelGLFW(w, xoffset, yoffset);
}

static void TW_GLFW3_Key(GLFWwindow *w, int key, int scancode, int action, int mods)
{
    // AntTweakBar only acts on key presses; forward auto-repeat as a press
    if( action==GLFW_REPEAT )
        action = GLFW_PRESS;
    TwEventKeyGLFW(w, key, scancode, action, mods);
}

static void TW_GLFW3_Char(GLFWwindow *w, unsigned int codepoint)
{
    TwEventCharGLFW(w, codepoint);
}

static void TW_GLFW3_FramebufferSize(GLFWwindow *w, int fbwidth, int fbheight)
{
    int winw, winh;
    TwWindowSize(fbwidth, fbheight);
    glfwGetWindowSize(w, &winw, &winh);
    g_ATBScaleX = winw>0 ? (double)fbwidth/winw : 1.0;
    g_ATBScaleY = winh>0 ? (double)fbheight/winh : 1.0;
}

// Initialize the GUI (core OpenGL backend) and forward GLFW 3 events to it.
// Returns false, with the reason printed, if initialization failed.
// Must be called with a current OpenGL context and after GLEW initialization.
static bool InitAntTweakBar(GLFWwindow *window)
{
    int fbw, fbh, winw, winh;
    glfwGetFramebufferSize(window, &fbw, &fbh);
    glfwGetWindowSize(window, &winw, &winh);
    g_ATBScaleX = winw>0 ? (double)fbw/winw : 1.0;
    g_ATBScaleY = winh>0 ? (double)fbh/winh : 1.0;

    if( !TwInit(TW_OPENGL_CORE, NULL) )
    {
        fprintf(stderr, "Failed to initialize AntTweakBar: %s\n", TwGetLastError());
        return false;
    }

    TwWindowSize(fbw, fbh);

    glfwSetMouseButtonCallback(window, TW_GLFW3_MouseButton);
    glfwSetCursorPosCallback(window, TW_GLFW3_CursorPos);
    glfwSetScrollCallback(window, TW_GLFW3_Scroll);
    glfwSetKeyCallback(window, TW_GLFW3_Key);
    glfwSetCharCallback(window, TW_GLFW3_Char);
    glfwSetFramebufferSizeCallback(window, TW_GLFW3_FramebufferSize);

    return true;
}

// True while the mouse is over an AntTweakBar element. The picking code of
// the tutorials uses it so that clicks on the GUI are not also sent to the
// scene.
static bool ATBMouseOverBar()
{
    return g_ATBMouseOverBar;
}

// Current window size in framebuffer pixels. glReadPixels and friend use
// framebuffer coordinates, which differ from the screen coordinates reported
// by GLFW on HiDPI displays.
static void ATBFramebufferSize(int *width, int *height)
{
    glfwGetFramebufferSize(glfwGetCurrentContext(), width, height);
}

#endif
