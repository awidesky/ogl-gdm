if(MSVC AND NOT "${MSVC_VERSION}" LESS 1400)
	add_definitions( "/MP" )
endif()


add_definitions(
	-DTW_STATIC
	-DTW_NO_LIB_PRAGMA
	-DTW_NO_DIRECT3D
	-DGLEW_STATIC
	-D_CRT_SECURE_NO_WARNINGS
)

### Opengl dependencies ###

set(GLFW_BUILD_DOCS OFF CACHE BOOL "Build the GLFW documentation")

set(GDM_WINDOW_BACKEND "glfw" CACHE STRING "")
set(GDM_GL_LOADER "glew-glad" CACHE STRING "")
set(GDM_USE_GLM ON CACHE BOOL "")

set(GDM_GLFW_VERSION "3.4.0" CACHE STRING "GLFW version")
set(GDM_GLEW_VERSION "2.3.1" CACHE STRING "GLEW version")
set(GDM_GLM_VERSION "1.0.3" CACHE STRING "GLM version")
set(AGL_LIBRARY "" CACHE FILEPATH "Disable AGL, deprecated Apple graphics framework." FORCE)

### GDM ###
# external/gdm is not a git checkout: FetchGDM() (FetchGDM.cmake) keeps a
# copy of the gdm sources here, tracking the head commit of GDM_TAG; see the
# header comment there for the resolve/download/verify/install pipeline.
set(GDM_SRC_DIR "${CMAKE_SOURCE_DIR}/external/gdm")
set(GDM_TAG "master" CACHE STRING "GDM's version; branch, tag, or commit hash")
include("${CMAKE_CURRENT_LIST_DIR}/FetchGDM.cmake")
FetchGDM("${GDM_SRC_DIR}" "${GDM_TAG}")

# gdm always lives at ${GDM_SRC_DIR} (a subdirectory of this source tree), so
# the one-arg form is valid; binary dir defaults to <build>/external/gdm.
add_subdirectory("${GDM_SRC_DIR}")
set(OPENGL_LIBRARY
	${OPENGL_LIBRARY}
	gdm::window # original script only add glfw, I don't know if ANTTWEAKBAR really need it, but..
)

if(${CMAKE_SYSTEM_NAME} MATCHES "Linux")
set(OPENGL_LIBRARY
	${OPENGL_LIBRARY}
	-lGL -lGLU -lXrandr -lXext -lX11 -lrt
	${CMAKE_DL_LIBS}
)
elseif(${CMAKE_SYSTEM_NAME} MATCHES "Darwin")
set(OPENGL_LIBRARY
	${OPENGL_LIBRARY}
	${CMAKE_DL_LIBS}
)
endif(${CMAKE_SYSTEM_NAME} MATCHES "Linux")


### ANTTWEAKBAR ###

set(ANTTWEAKBAR_SOURCE
	AntTweakBar-1.16/src/LoadOGL.cpp
	AntTweakBar-1.16/src/LoadOGLCore.cpp
	AntTweakBar-1.16/src/TwColors.cpp
	AntTweakBar-1.16/src/TwBar.cpp
	AntTweakBar-1.16/src/TwEventGLFW.c
	AntTweakBar-1.16/src/TwFonts.cpp
	AntTweakBar-1.16/src/TwMgr.cpp
	AntTweakBar-1.16/src/TwOpenGL.cpp
	AntTweakBar-1.16/src/TwOpenGLCore.cpp
	AntTweakBar-1.16/src/TwPrecomp.cpp
)

if(${CMAKE_SYSTEM_NAME} MATCHES "Darwin") # If on Xcode, rename files to .mm
file(COPY ${ANTTWEAKBAR_SOURCE} DESTINATION AntTweakBar-ObjectiveC/)
file(RENAME ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/LoadOGL.cpp      ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/LoadOGL.mm     )
file(RENAME ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/LoadOGLCore.cpp  ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/LoadOGLCore.mm )
file(RENAME ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwColors.cpp     ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwColors.mm    )
file(RENAME ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwBar.cpp        ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwBar.mm       )
file(RENAME ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwEventGLFW.c    ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwEventGLFW.m  )
file(RENAME ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwFonts.cpp      ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwFonts.mm     )
file(RENAME ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwMgr.cpp        ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwMgr.mm       )
file(RENAME ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwOpenGL.cpp     ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwOpenGL.mm    )
file(RENAME ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwOpenGLCore.cpp ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwOpenGLCore.mm)
file(RENAME ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwPrecomp.cpp    ${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwPrecomp.mm   )

set(ANTTWEAKBAR_SOURCE
	${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/LoadOGL.mm
	${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/LoadOGLCore.mm
	${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwColors.mm
	${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwBar.mm
	${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwEventGLFW.m
	${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwFonts.mm
	${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwMgr.mm
	${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwOpenGL.mm
	${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwOpenGLCore.mm
	${CMAKE_BINARY_DIR}/external/AntTweakBar-ObjectiveC/TwPrecomp.mm
)
include_directories(
	${CMAKE_SOURCE_DIR}/external/AntTweakBar-1.16/src/
)
add_definitions(
	-D_MACOSX
)
elseif(${CMAKE_SYSTEM_NAME} MATCHES "Linux")
add_definitions(
	-D_UNIX
)
elseif(${CMAKE_SYSTEM_NAME} MATCHES "Windows")
add_definitions(
	-D_WINDOWS
)

endif(${CMAKE_SYSTEM_NAME} MATCHES "Darwin")


set(ANTTWEAKBAR_HEADERS
	AntTweakBar-1.16/src/AntPerfTimer.h
	AntTweakBar-1.16/src/LoadOGL.h
	AntTweakBar-1.16/src/LoadOGLCore.h
	AntTweakBar-1.16/src/MiniGLFW.h
	AntTweakBar-1.16/src/resource.h
	AntTweakBar-1.16/src/TwBar.h
	AntTweakBar-1.16/src/TwColors.h
	AntTweakBar-1.16/src/TwFonts.h
	AntTweakBar-1.16/src/TwGraph.h
	AntTweakBar-1.16/src/TwMgr.h
	AntTweakBar-1.16/src/TwOpenGL.h
	AntTweakBar-1.16/src/TwOpenGLCore.h
	AntTweakBar-1.16/src/TwPrecomp.h
)

include_directories(
	AntTweakBar-1.16/include/
)

add_library( ANTTWEAKBAR_116_OGLCORE_GLFW STATIC
	${ANTTWEAKBAR_SOURCE}
	${ANTTWEAKBAR_HEADERS}
)

target_link_libraries(ANTTWEAKBAR_116_OGLCORE_GLFW
	${OPENGL_LIBRARY}
	${EXTRA_LIBS}
)
if(${CMAKE_SYSTEM_NAME} MATCHES "Darwin")
	# TwMgr.mm uses AppKit (NSCursor, NSImage, NSPasteboard) and the ObjC runtime.
	# Without these the final link fails with undefined _OBJC_CLASS_$_NS* / _objc_msgSend symbols.
	target_link_libraries(ANTTWEAKBAR_116_OGLCORE_GLFW
		"-framework AppKit"
		"-framework Foundation"
	)
endif()
target_compile_options(ANTTWEAKBAR_116_OGLCORE_GLFW PRIVATE "$<$<CXX_COMPILER_ID:MSVC>:/source-charset:windows-1252>")

### ASSIMP ###
# use_or_fetch_package() is defined in gdm's directory scope; pull in its definition.
include("${GDM_SRC_DIR}/cmake/Dependencies.cmake")

# AssImp 6 dropped BUILD_STATIC_LIB (the old build forced it ON); its only selector
# is BUILD_SHARED_LIBS, which defaults ON. Normal variable on purpose, unset below:
# scoped to the fetched subtree, and a user's -DBUILD_SHARED_LIBS=... is left as-is
# for the rest of this file.
set(BUILD_SHARED_LIBS OFF)
set(ASSIMP_BUILD_TESTS OFF)                    # default ON in 6.x
set(ASSIMP_INSTALL OFF)                        # default ON in 6.x
set(ASSIMP_NO_EXPORT ON)                       # import-only: also drops the export framework
set(ASSIMP_WARNINGS_AS_ERRORS OFF)             # default ON; -Werror would break on a new compiler
# zlib: assimp always links one; keep its platform default (bundled on Windows,
# system zlib on macOS/Linux). The bundled 1.2.13 does not compile with recent
# macOS SDKs (zutil.h's fdopen macro clashes with <stdio.h>).
set(ASSIMP_BUILD_DRACO OFF)
set(ASSIMP_BUILD_ALL_IMPORTERS_BY_DEFAULT OFF) # core + only the importer this repo uses
set(ASSIMP_BUILD_OBJ_IMPORTER ON)
set(CMAKE_DISABLE_FIND_PACKAGE_PkgConfig ON)
# Always build the fetched source (target 'assimp'); an installed assimp (vcpkg on
# Windows, etc.) would be found and expose only 'assimp::assimp', breaking the link.
set(CMAKE_DISABLE_FIND_PACKAGE_assimp ON)
use_or_fetch_package(NAME assimp VERSION 6.0.5
	GIT_REPOSITORY https://github.com/assimp/assimp
	GIT_TAG v6.0.5
	CANDIDATE_TARGETS assimp)
unset(CMAKE_DISABLE_FIND_PACKAGE_PkgConfig)
unset(CMAKE_DISABLE_FIND_PACKAGE_assimp)
unset(BUILD_SHARED_LIBS)

### BULLET ###
# Bullet already has a CMakeLists.txt so let's use these

set(BULLET_VERSION 2.81)
include_directories(
	bullet-2.81-rev2613/src
)
add_subdirectory( bullet-2.81-rev2613/src/BulletSoftBody )
add_subdirectory( bullet-2.81-rev2613/src/BulletCollision )
add_subdirectory( bullet-2.81-rev2613/src/BulletDynamics )
add_subdirectory( bullet-2.81-rev2613/src/LinearMath )

target_compile_options(BulletSoftBody PRIVATE "$<$<CXX_COMPILER_ID:MSVC>:/source-charset:windows-1252>")
target_compile_options(BulletCollision PRIVATE "$<$<CXX_COMPILER_ID:MSVC>:/source-charset:windows-1252>")

