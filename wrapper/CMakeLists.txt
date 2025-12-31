cmake_minimum_required(VERSION 3.25)

if(APPLE)
    # Treat target as Linux/Android to avoid Apple-specific linker flags (e.g., -search_paths_first)
    set(CMAKE_SYSTEM_NAME "Linux" CACHE STRING "Target system for cross-compiling" FORCE)
    set(CMAKE_EXE_LINKER_FLAGS "" CACHE STRING "Disabled Apple linker defaults" FORCE)
    set(CMAKE_SHARED_LINKER_FLAGS "" CACHE STRING "Disabled Apple linker defaults" FORCE)
    set(CMAKE_MODULE_LINKER_FLAGS "" CACHE STRING "Disabled Apple linker defaults" FORCE)
endif()

# Avoid macOS default arch flags when cross-compiling
if(APPLE)
    set(CMAKE_OSX_ARCHITECTURES "" CACHE STRING "Disabled for cross-compiling" FORCE)
endif()

set(ANDROID_NDK_PATH "" CACHE PATH "Path to Android NDK")
if(NOT ANDROID_NDK_PATH)
    if(DEFINED ENV{ANDROID_NDK_HOME})
        set(ANDROID_NDK_PATH "$ENV{ANDROID_NDK_HOME}")
    elseif(DEFINED ENV{ANDROID_NDK_ROOT})
        set(ANDROID_NDK_PATH "$ENV{ANDROID_NDK_ROOT}")
    else()
        set(ANDROID_NDK_PATH "$ENV{HOME}/android-ndk-r23b")
    endif()
endif()
if(NOT EXISTS "${ANDROID_NDK_PATH}")
    message(FATAL_ERROR "Android NDK not found at ${ANDROID_NDK_PATH}. Set ANDROID_NDK_PATH/ANDROID_NDK_HOME/ANDROID_NDK_ROOT.")
endif()

set(ANDROID_ARCH "x86_64" CACHE STRING "Android target arch (x86_64 or aarch64)")
if(NOT ANDROID_ARCH STREQUAL "x86_64" AND NOT ANDROID_ARCH STREQUAL "aarch64")
    message(FATAL_ERROR "Unsupported ANDROID_ARCH=${ANDROID_ARCH}. Supported: x86_64, aarch64.")
endif()
set(ANDROID_API "22" CACHE STRING "Android API level")

set(ANDROID_NDK_HOST_TAG "" CACHE STRING "NDK host tag (darwin-arm64, darwin-x86_64, linux-x86_64, linux-aarch64)")
set(_ndk_host_candidates "")
if(ANDROID_NDK_HOST_TAG)
    list(APPEND _ndk_host_candidates "${ANDROID_NDK_HOST_TAG}")
endif()
if(CMAKE_HOST_SYSTEM_NAME STREQUAL "Darwin")
    if(CMAKE_HOST_SYSTEM_PROCESSOR MATCHES "arm64|aarch64")
        list(APPEND _ndk_host_candidates "darwin-arm64" "darwin-x86_64")
    else()
        list(APPEND _ndk_host_candidates "darwin-x86_64" "darwin-arm64")
    endif()
elseif(CMAKE_HOST_SYSTEM_NAME STREQUAL "Linux")
    if(CMAKE_HOST_SYSTEM_PROCESSOR MATCHES "arm64|aarch64")
        list(APPEND _ndk_host_candidates "linux-aarch64" "linux-x86_64")
    else()
        list(APPEND _ndk_host_candidates "linux-x86_64" "linux-aarch64")
    endif()
else()
    message(FATAL_ERROR "Unsupported host platform: ${CMAKE_HOST_SYSTEM_NAME}")
endif()
list(REMOVE_DUPLICATES _ndk_host_candidates)

set(_resolved_ndk_host_tag "")
foreach(_tag IN LISTS _ndk_host_candidates)
    if(EXISTS "${ANDROID_NDK_PATH}/toolchains/llvm/prebuilt/${_tag}")
        set(_resolved_ndk_host_tag "${_tag}")
        break()
    endif()
endforeach()
if(NOT _resolved_ndk_host_tag)
    string(REPLACE ";" ", " _candidates_pretty "${_ndk_host_candidates}")
    message(FATAL_ERROR "NDK toolchain not found for host tag candidates: ${_candidates_pretty}. Set ANDROID_NDK_PATH or ANDROID_NDK_HOST_TAG.")
endif()
set(ANDROID_NDK_HOST_TAG "${_resolved_ndk_host_tag}" CACHE STRING "NDK host tag (darwin-arm64, darwin-x86_64, linux-x86_64, linux-aarch64)" FORCE)

if(ANDROID_ARCH STREQUAL "x86_64")
    set(ANDROID_TRIPLE "x86_64-linux-android")
    set(WRAPPER_LINUX_TARGET_DEFAULT "x86_64-linux-gnu")
else()
    set(ANDROID_TRIPLE "aarch64-linux-android")
    set(WRAPPER_LINUX_TARGET_DEFAULT "aarch64-linux-gnu")
endif()
set(CMAKE_SYSTEM_PROCESSOR "${ANDROID_ARCH}" CACHE STRING "Target processor for cross-compiling" FORCE)

set(TOOLCHAIN "${ANDROID_NDK_PATH}/toolchains/llvm/prebuilt/${ANDROID_NDK_HOST_TAG}")

set(CMAKE_C_COMPILER "${TOOLCHAIN}/bin/${ANDROID_TRIPLE}${ANDROID_API}-clang" CACHE FILEPATH "C compiler" FORCE)
set(CMAKE_CXX_COMPILER "${TOOLCHAIN}/bin/${ANDROID_TRIPLE}${ANDROID_API}-clang++" CACHE FILEPATH "C++ compiler" FORCE)
set(C_COMPILER "${TOOLCHAIN}/bin/clang")
if(APPLE)
    set(CMAKE_C_LINK_EXECUTABLE "<CMAKE_C_COMPILER> <FLAGS> <CMAKE_C_LINK_FLAGS> <LINK_FLAGS> <OBJECTS> -o <TARGET> <LINK_LIBRARIES>")
    set(CMAKE_CXX_LINK_EXECUTABLE "<CMAKE_CXX_COMPILER> <FLAGS> <CMAKE_CXX_LINK_FLAGS> <LINK_FLAGS> <OBJECTS> -o <TARGET> <LINK_LIBRARIES>")
endif()

project(wrapper LANGUAGES C CXX)
include(ExternalProject)

set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD 11)

set(WRAPPER_LINUX_TARGET "$ENV{WRAPPER_LINUX_TARGET}" CACHE STRING "Target triple for wrapper Linux binary")
if(WRAPPER_LINUX_TARGET STREQUAL "")
    set(WRAPPER_LINUX_TARGET "${WRAPPER_LINUX_TARGET_DEFAULT}" CACHE STRING "Target triple for wrapper Linux binary" FORCE)
endif()

set(WRAPPER_CC "$ENV{WRAPPER_CC}" CACHE STRING "C compiler for wrapper (Linux host binary)")
set(WRAPPER_CC_FLAGS "$ENV{WRAPPER_CC_FLAGS}" CACHE STRING "Extra flags for wrapper compiler")
string(TOLOWER "${CMAKE_HOST_SYSTEM_PROCESSOR}" _host_cpu)
if(_host_cpu STREQUAL "amd64")
    set(_host_cpu "x86_64")
elseif(_host_cpu STREQUAL "arm64")
    set(_host_cpu "aarch64")
endif()
string(REGEX REPLACE "^([^-]+)-.*" "\\1" _wrapper_target_cpu "${WRAPPER_LINUX_TARGET}")
string(TOLOWER "${_wrapper_target_cpu}" _wrapper_target_cpu)
set(_host_matches_wrapper_target OFF)
if((_host_cpu STREQUAL "x86_64" AND _wrapper_target_cpu STREQUAL "x86_64") OR
   (_host_cpu STREQUAL "aarch64" AND _wrapper_target_cpu STREQUAL "aarch64"))
    set(_host_matches_wrapper_target ON)
endif()

if(WRAPPER_CC STREQUAL "")
    if(CMAKE_HOST_SYSTEM_NAME STREQUAL "Linux" AND _host_matches_wrapper_target)
        set(WRAPPER_CC "cc")
    else()
        find_program(ZIG_EXECUTABLE zig)
        if(NOT ZIG_EXECUTABLE)
            message(FATAL_ERROR "zig is required to cross-compile the wrapper on ${CMAKE_HOST_SYSTEM_NAME}. Install zig or set WRAPPER_CC/WRAPPER_CC_FLAGS to a compiler that can target ${WRAPPER_LINUX_TARGET}.")
        endif()
        set(WRAPPER_CC "${ZIG_EXECUTABLE}")
    endif()
endif()

if(WRAPPER_CC_FLAGS STREQUAL "" AND (NOT _host_matches_wrapper_target OR NOT CMAKE_HOST_SYSTEM_NAME STREQUAL "Linux"))
    set(WRAPPER_CC_FLAGS "cc -target ${WRAPPER_LINUX_TARGET}")
endif()
set(WRAPPER_CC_FLAGS_LIST "${WRAPPER_CC_FLAGS}")
separate_arguments(WRAPPER_CC_FLAGS_LIST)

set(CMDLINE_SOURCE cmdline.c)
set(HANDLE_SOURCE main.cpp)
set(CJSON_SOURCE cjson/cjson.c)
set(MAIN_SOURCE main.c)
set(WRAPPER_SOURCE wrapper.c)

add_library(cmdline_object OBJECT ${CMDLINE_SOURCE})
add_library(handle_object OBJECT ${HANDLE_SOURCE})
add_library(cjson_object OBJECT ${CJSON_SOURCE})

add_executable(main ${MAIN_SOURCE} $<TARGET_OBJECTS:cmdline_object> $<TARGET_OBJECTS:handle_object> $<TARGET_OBJECTS:cjson_object>)

set_target_properties(main PROPERTIES 
    COMPILE_DEFINITIONS "MyRelease"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/rootfs/system/bin"
)

find_library(ANDROIDAPPMUSIC_LIB androidappmusic PATHS ${CMAKE_SOURCE_DIR}/rootfs/system/lib64)
find_library(STORESERVICESCORE_LIB storeservicescore PATHS ${CMAKE_SOURCE_DIR}/rootfs/system/lib64)
find_library(MEDIAPLATFORM_LIB mediaplatform PATHS ${CMAKE_SOURCE_DIR}/rootfs/system/lib64)
find_library(CXX_SHARED_LIB c++_shared PATHS ${CMAKE_SOURCE_DIR}/rootfs/system/lib64)
find_library(CURL_SHARED_LIB curl PATHS ${CMAKE_SOURCE_DIR}/rootfs/system/lib64)
find_library(LOG_SHARED_LIB log PATHS ${CMAKE_SOURCE_DIR}/rootfs/system/lib64)

# Link libraries
target_link_libraries(main
    ${CXX_SHARED_LIB}
    ${ANDROIDAPPMUSIC_LIB}
    ${STORESERVICESCORE_LIB}
    ${MEDIAPLATFORM_LIB}
)

get_target_property(MAIN_COMPILE_DEFINITIONS main COMPILE_DEFINITIONS)
if(NOT "MyRelease" IN_LIST MAIN_COMPILE_DEFINITIONS)
    target_link_libraries(main
        ${LOG_SHARED_LIB}
        ${CURL_SHARED_LIB}
    )
    set(CMAKE_C_FLAGS "-Werror -g")
    set(CMAKE_CXX_FLAGS "-Werror -g")
else()
    set(CMAKE_C_FLAGS "-Wall -Werror")
    set(CMAKE_CXX_FLAGS "-Wall -Werror")
endif()

link_directories(${CMAKE_SOURCE_DIR}/rootfs/system/lib64)

file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/zig-cache")

ExternalProject_Add(
    wrapper
    PREFIX ${CMAKE_BINARY_DIR}
    SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}
    CONFIGURE_COMMAND ""
    BUILD_COMMAND ${CMAKE_COMMAND} -E env ZIG_LOCAL_CACHE_DIR=${CMAKE_BINARY_DIR}/zig-cache ZIG_GLOBAL_CACHE_DIR=${CMAKE_BINARY_DIR}/zig-cache ${WRAPPER_CC} ${WRAPPER_CC_FLAGS_LIST} -O3 -Wall -o wrapper ${WRAPPER_SOURCE} ${CMAKE_CURRENT_SOURCE_DIR}/cmdline.c
    BUILD_IN_SOURCE 1
    INSTALL_COMMAND ""
    DEPENDS main
)
