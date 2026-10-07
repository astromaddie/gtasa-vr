cmake_minimum_required(VERSION 3.22)
project(savr LANGUAGES CXX ASM)

# Player builds omit developer diagnostics. Enable explicitly for local captures;
# the profiler remains hidden until selected in the menu or toggled by grips+A.
option(SAVR_DEV "Developer build: logging, FPS panel, full version" OFF)
if(SAVR_DEV)
    add_compile_definitions(SAVR_DEV=1)
endif()

# Valve Steam Frame (Lepton, Android 11 container) variant: Frame manifest and
# OpenXR input profiles, relocated storage root, logging left on for bring-up.
# Quest builds leave this OFF and are unchanged.
option(SAVR_STEAM_FRAME "Steam Frame (Lepton) build variant" OFF)
if(SAVR_STEAM_FRAME)
    add_compile_definitions(SAVR_STEAM_FRAME=1)
    enable_language(C)
endif()

# Keep the producer-backpressure implementation available in normal builds.
# Its runtime property remains opt-in, so an ordinary player run pays no
# atomic traffic while diagnostics can still enable it without rebuilding.
option(SAVR_EXPERIMENTAL_BACKPRESSURE
    "Experimental XR-to-GameThread stereo producer backpressure" ON)
if(SAVR_EXPERIMENTAL_BACKPRESSURE)
    add_compile_definitions(SAVR_EXPERIMENTAL_BACKPRESSURE=1)
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(OPENXR_DIR ${CMAKE_CURRENT_SOURCE_DIR}/vendor/openxr)

# The OpenXR loader binary is not committed to the public source kit. The
# build wizard downloads the exact Khronos 1.1.43 AAR, verifies it, and
# passes its arm64 library via OPENXR_LOADER_SO (flag or environment).
# A tree that does carry the loader under vendor/openxr/lib/<abi>/ is used
# as-is when nothing is passed.
set(OPENXR_LOADER_SO "" CACHE FILEPATH
    "Path to the Khronos Android arm64-v8a libopenxr_loader.so")
if(NOT OPENXR_LOADER_SO AND DEFINED ENV{SAVR_OPENXR_LOADER_SO})
    set(OPENXR_LOADER_SO "$ENV{SAVR_OPENXR_LOADER_SO}")
endif()
if(NOT OPENXR_LOADER_SO)
    set(OPENXR_LOADER_SO "${OPENXR_DIR}/lib/${ANDROID_ABI}/libopenxr_loader.so")
endif()
if(NOT EXISTS "${OPENXR_LOADER_SO}")
    message(FATAL_ERROR
        "OPENXR_LOADER_SO must point to the verified Khronos 1.1.43 "
        "arm64-v8a libopenxr_loader.so. Run BUILD_AND_INSTALL or pass "
        "-DOPENXR_LOADER_SO=<path>.")
endif()

add_library(openxr_loader SHARED IMPORTED)
set_target_properties(openxr_loader PROPERTIES
    IMPORTED_LOCATION "${OPENXR_LOADER_SO}"
)

add_library(savr SHARED
    src/main.cpp
    src/AircraftHlod.cpp
    src/AircraftHlodData.S
    src/AnimatedTextures.cpp
    src/Appearance.cpp
    src/Symbols.cpp
    src/SetupMapDrawDistanceBridge.S
    src/EyeDepth.cpp
    src/VrCamera.cpp
    src/VrFire.cpp
    src/Xr.cpp
    src/Cheats.cpp
    src/HudSettings.cpp
    src/Hydraulics.cpp
    src/Jetpack.cpp
    src/Locomotion.cpp
    src/Driving.cpp
    src/GestureMove.cpp
    src/Swimming.cpp
    src/ThirdPersonMove.cpp
    src/BoatEntry.cpp
    src/GraphicsEffects.cpp
    src/Basketball.cpp
    src/MapZoom.cpp
    src/BrainDiag.cpp
    src/HdWeapons.cpp
    src/ModelSets.cpp
    src/LoadingTrace.cpp
    src/Holster.cpp
    src/Melee.cpp
    src/MissionControls.cpp
    src/Catalyst.cpp
    src/JustBusiness.cpp
    src/BeachDance.cpp
    src/Tbone.cpp
    src/MissionScenes.cpp
    src/PerfTelemetry.cpp
    src/PhysicalWeapon.cpp
    src/Pickups.cpp
    src/ScopeAim.cpp
    src/Throwable.cpp
    src/TrafficCensus.cpp
    src/Weapon.cpp
    src/Calib.cpp
)

# Track the generated .incbin payload explicitly so pack changes rebuild the object.
set(AIRCRAFT_HLOD_PACK
    "${CMAKE_BINARY_DIR}/../aircraft-hlod-global/aircraft.hlod")
set_property(SOURCE src/AircraftHlodData.S PROPERTY OBJECT_DEPENDS
    "${AIRCRAFT_HLOD_PACK}")

if(SAVR_STEAM_FRAME)
    target_sources(savr PRIVATE src/CameraComfort.cpp
        vendor/sfvr/src/sfvr_adjust.c vendor/sfvr/src/sfvr_camera.c)
    target_include_directories(savr PRIVATE vendor/sfvr/include)
endif()

target_include_directories(savr PRIVATE src ${OPENXR_DIR}/include)

# -fvisibility=hidden keeps our own symbol table down to the JNI entry points, so
# nothing of ours can accidentally shadow a game symbol during resolution.
target_compile_options(savr PRIVATE
    -Wall -Wextra -Wno-unused-parameter -Wno-missing-field-initializers
    -fvisibility=hidden
    $<$<CONFIG:Release>:-O2>
)

find_library(log-lib log)
find_library(android-lib android)
find_library(egl-lib EGL)
find_library(gles-lib GLESv3)

target_link_libraries(savr PRIVATE
    openxr_loader
    ${log-lib} ${android-lib} ${egl-lib} ${gles-lib}
)
