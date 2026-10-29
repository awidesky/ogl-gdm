//  ---------------------------------------------------------------------------
//
//  @file       TwEventGLFW.c
//  @brief      Helper: 
//              translate and re-send mouse and keyboard events 
//              from GLFW event callbacks to AntTweakBar
//  
//  @author     Philippe Decaudin
//  @license    This file is part of the AntTweakBar library.
//              For conditions of distribution and use, see License.txt
//
//  ---------------------------------------------------------------------------

// #include <GL/glfw.h>
#include "MiniGLFW.h" // a subset of GLFW.h needed to compile TwEventGLFW.c
// note: AntTweakBar.dll does not need to link with GLFW, 
// it just needs some definitions for its helper functions.

#include <AntTweakBar.h>


int TW_CALL TwEventMouseButtonGLFW(GLFWwindow * glfwWindow, int glfwButton, int glfwAction, int glfwModifierKeys)
{
    int handled = 0;
    TwMouseAction action = (glfwAction==GLFW_PRESS) ? TW_MOUSE_PRESSED : TW_MOUSE_RELEASED;

    if( glfwButton==GLFW_MOUSE_BUTTON_LEFT )
        handled = TwMouseButton(action, TW_MOUSE_LEFT);
    else if( glfwButton==GLFW_MOUSE_BUTTON_RIGHT )
        handled = TwMouseButton(action, TW_MOUSE_RIGHT);
    else if( glfwButton==GLFW_MOUSE_BUTTON_MIDDLE )
        handled = TwMouseButton(action, TW_MOUSE_MIDDLE);

    return handled;
}


int g_KMod = 0;


int TW_CALL TwEventKeyGLFW(GLFWwindow * glfwWindow, int glfwKey, int glfwScancode, int glfwAction, int glfwModifierKeys)
{
    int handled = 0;
    if( glfwKey<0 )
        return 0;

    // Register of modifiers state (GLFW 3 reports the modifiers with every
    // key event, so there is no need to track the shift/ctrl/alt keys here)
    g_KMod = 0;
    if( glfwModifierKeys & GLFW_MOD_SHIFT )
        g_KMod |= TW_KMOD_SHIFT;
    if( glfwModifierKeys & GLFW_MOD_CONTROL )
        g_KMod |= TW_KMOD_CTRL;
    if( glfwModifierKeys & GLFW_MOD_ALT )
        g_KMod |= TW_KMOD_ALT;

    // Process key pressed
    if( glfwAction==GLFW_PRESS )
    {
        int mod = g_KMod;
        int testkp = ((mod&TW_KMOD_CTRL) || (mod&TW_KMOD_ALT)) ? 1 : 0;

        if( (mod&TW_KMOD_CTRL) && glfwKey>0 && glfwKey<GLFW_KEY_SPECIAL )   // CTRL cases
            handled = TwKeyPressed(glfwKey, mod);
        else if( glfwKey>=GLFW_KEY_SPECIAL )
        {
            int k = 0;

            if( glfwKey>=GLFW_KEY_F1 && glfwKey<=GLFW_KEY_F15 )
                k = TW_KEY_F1 + (glfwKey-GLFW_KEY_F1);
            else if( testkp && glfwKey>=GLFW_KEY_KP_0 && glfwKey<=GLFW_KEY_KP_9 )
                k = '0' + (glfwKey-GLFW_KEY_KP_0);
            else
            {
                switch( glfwKey )
                {
                case GLFW_KEY_ESCAPE:
                    k = TW_KEY_ESCAPE;
                    break;
                case GLFW_KEY_UP:
                    k = TW_KEY_UP;
                    break;
                case GLFW_KEY_DOWN:
                    k = TW_KEY_DOWN;
                    break;
                case GLFW_KEY_LEFT:
                    k = TW_KEY_LEFT;
                    break;
                case GLFW_KEY_RIGHT:
                    k = TW_KEY_RIGHT;
                    break;
                case GLFW_KEY_TAB:
                    k = TW_KEY_TAB;
                    break;
                case GLFW_KEY_ENTER:
                    k = TW_KEY_RETURN;
                    break;
                case GLFW_KEY_BACKSPACE:
                    k = TW_KEY_BACKSPACE;
                    break;
                case GLFW_KEY_INSERT:
                    k = TW_KEY_INSERT;
                    break;
                case GLFW_KEY_DELETE:
                    k = TW_KEY_DELETE;
                    break;
                case GLFW_KEY_PAGE_UP:
                    k = TW_KEY_PAGE_UP;
                    break;
                case GLFW_KEY_PAGE_DOWN:
                    k = TW_KEY_PAGE_DOWN;
                    break;
                case GLFW_KEY_HOME:
                    k = TW_KEY_HOME;
                    break;
                case GLFW_KEY_END:
                    k = TW_KEY_END;
                    break;
                case GLFW_KEY_KP_ENTER:
                    k = TW_KEY_RETURN;
                    break;
                case GLFW_KEY_KP_DIVIDE:
                    if( testkp )
                        k = '/';
                    break;
                case GLFW_KEY_KP_MULTIPLY:
                    if( testkp )
                        k = '*';
                    break;
                case GLFW_KEY_KP_SUBTRACT:
                    if( testkp )
                        k = '-';
                    break;
                case GLFW_KEY_KP_ADD:
                    if( testkp )
                        k = '+';
                    break;
                case GLFW_KEY_KP_DECIMAL:
                    if( testkp )
                        k = '.';
                    break;
                case GLFW_KEY_KP_EQUAL:
                    if( testkp )
                        k = '=';
                    break;
                }
            }

            if( k>0 )
                handled = TwKeyPressed(k, mod);
        }
    }

    return handled;
}


int TW_CALL TwEventCharGLFW(GLFWwindow * glfwWindow, unsigned int glfwChar)
{
    // GLFW 3 reports Unicode code points; AntTweakBar fonts cover the
    // printable Latin-1 range only. Control characters (< 32) are handled
    // through the key callback (and must not be injected twice, e.g. when
    // GLFW maps Ctrl+letter to the 0x01..0x1A range).
    if( glfwChar>=32 && (glfwChar & 0xff00)==0 )
        return TwKeyPressed((int)glfwChar, g_KMod);

    return 0;
}

int TW_CALL TwEventMousePosGLFW(GLFWwindow * glfwWindow, double xpos, double ypos){
	return TwMouseMotion((int)xpos, (int)ypos);
}

int TW_CALL TwEventMouseWheelGLFW(GLFWwindow * glfwWindow, double xoffset, double yoffset){
	// GLFW 3 reports per-event wheel deltas while AntTweakBar expects an
	// accumulated wheel position (like the SDL and Win32 helpers below),
	// so accumulate the deltas before forwarding.
	static int s_WheelPos = 0;
	s_WheelPos += (int)yoffset;
	return TwMouseWheel(s_WheelPos);
}


// functions with __cdecl calling convension
TW_API int TW_CDECL_CALL TwEventMouseButtonGLFWcdecl(int glfwButton, int glfwAction)
{
    return TwEventMouseButtonGLFW(NULL, glfwButton, glfwAction, 0);
}
TW_API int TW_CDECL_CALL TwEventKeyGLFWcdecl(int glfwKey, int glfwAction)
{
    return TwEventKeyGLFW(NULL, glfwKey, 0, glfwAction, 0);
}
TW_API int TW_CDECL_CALL TwEventCharGLFWcdecl(int glfwChar, int glfwAction)
{
    if( glfwAction==GLFW_PRESS )
        return TwEventCharGLFW(NULL, (unsigned int)glfwChar);

    return 0;
}
TW_API int TW_CDECL_CALL TwEventMousePosGLFWcdecl(int mouseX, int mouseY)
{
    return TwMouseMotion(mouseX, mouseY);
}
TW_API int TW_CDECL_CALL TwEventMouseWheelGLFWcdecl(int wheelPos)
{
    return TwMouseWheel(wheelPos);
}
