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

# TODO : use file(DOWNLOAD)
include(FetchContent)
set(FETCHCONTENT_UPDATES_DISCONNECTED ON CACHE BOOL "" FORCE)

# Keep gdm in sync with upstream master at configure time
# The fetch is quiet; the worktree is hard-reset only when behind origin/master,
# which also wipes any unintended local edits in external/gdm.
set(GDM_SRC_DIR "${CMAKE_SOURCE_DIR}/external/gdm")
if(EXISTS "${GDM_SRC_DIR}/.git")
	find_package(Git QUIET)
	if(NOT Git_FOUND)
		message(WARNING "GDM: Git not found in system; GDM may be outdated")
	else()
		execute_process(
			COMMAND "${GIT_EXECUTABLE}" fetch --quiet origin "+refs/heads/master:refs/remotes/origin/master"
			WORKING_DIRECTORY "${GDM_SRC_DIR}"
			ENVIRONMENT "GIT_TERMINAL_PROMPT=0"
			RESULT_VARIABLE _gdm_fetch_result
			ERROR_VARIABLE _gdm_fetch_err
			ERROR_STRIP_TRAILING_WHITESPACE
		)
		if(NOT _gdm_fetch_result EQUAL 0)
			message(WARNING "GDM: fetch from origin failed (${_gdm_fetch_err}); using existing checkout")
		else()
			execute_process(
				COMMAND "${GIT_EXECUTABLE}" rev-parse HEAD origin/master
				WORKING_DIRECTORY "${GDM_SRC_DIR}"
				RESULT_VARIABLE _gdm_rev_result
				OUTPUT_VARIABLE _gdm_rev_out
				OUTPUT_STRIP_TRAILING_WHITESPACE
			)
			if(NOT _gdm_rev_result EQUAL 0)
				message(WARNING "GDM: cannot compare HEAD with origin/master; using existing checkout")
			else()
				string(REPLACE "\n" ";" _gdm_rev "${_gdm_rev_out}")
				list(GET _gdm_rev 0 _gdm_head_sha)
				list(GET _gdm_rev 1 _gdm_upstream_sha)
				string(SUBSTRING "${_gdm_head_sha}" 0 7 _gdm_head_short)
				string(SUBSTRING "${_gdm_upstream_sha}" 0 7 _gdm_upstream_short)
				if(_gdm_head_sha STREQUAL _gdm_upstream_sha)
					message(STATUS "GDM is up to date (${_gdm_head_short})")
				else()
					message(STATUS "GDM: update ${_gdm_head_short} -> ${_gdm_upstream_short}")
					execute_process(
						COMMAND "${GIT_EXECUTABLE}" reset --hard origin/master
						WORKING_DIRECTORY "${GDM_SRC_DIR}"
						ENVIRONMENT "GIT_TERMINAL_PROMPT=0"
						RESULT_VARIABLE _gdm_reset_result
					)
					if(NOT _gdm_reset_result EQUAL 0)
						message(WARNING "GDM: reset --hard failed; keeping existing checkout")
					endif()
				endif()
			endif()
		endif()
	endif()
endif()

FetchContent_Declare(
	gdm
	GIT_REPOSITORY https://github.com/awidesky/gdm.git
	GIT_TAG        master
	GIT_SHALLOW    TRUE
	SOURCE_DIR     ${GDM_SRC_DIR}
	DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
FetchContent_MakeAvailable(gdm)
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
target_compile_options(ANTTWEAKBAR_116_OGLCORE_GLFW PRIVATE "$<$<CXX_COMPILER_ID:MSVC>:/source-charset:windows-1252>")

### ASSIMP ###
# AssImp already has a CMakeLists.txt so let's use these

# Compile built-in, modified version of Zlib
include(CheckIncludeFile)
include(CheckTypeSize)
include(CheckFunctionExists)
add_subdirectory( assimp-3.0.1270/contrib/zlib )

# Compile without Boost
include_directories( assimp-3.0.1270/code/BoostWorkaround )
add_definitions( -DASSIMP_BUILD_BOOST_WORKAROUND )

# Compile AssImp
set( LIB_INSTALL_DIR "lib")
set(LIBASSIMP_COMPONENT libassimp3.0-r1270-OGLtuts)
set(ZLIB_LIBRARIES zlib)
set(BUILD_STATIC_LIB ON)
#set(ZLIB_INCLUDE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/3rdparty/zlib)
add_subdirectory( assimp-3.0.1270/code )
target_compile_options(assimp PRIVATE "$<$<CXX_COMPILER_ID:MSVC>:/source-charset:windows-1252>")

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

