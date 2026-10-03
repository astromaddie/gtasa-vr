#pragma once

#include <android/log.h>

// Everything this mod prints goes under one tag so `logcat -s SAVR` is the whole
// picture and nothing of ours hides in the game's own noise.
#define SAVR_TAG "SAVR"

// Developer builds (-DSAVR_DEV=ON) log everything; player builds stay quiet
// except for real errors, so a shipped headset does not spend time or storage
// narrating internals.
//
// Steam Frame builds (-DSAVR_STEAM_FRAME=ON) keep LOGI/LOGW on as well: the
// platform bring-up depends on logcat output from a shipped-style package.
#if defined(SAVR_DEV) || defined(SAVR_STEAM_FRAME)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  SAVR_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  SAVR_TAG, __VA_ARGS__)
#else
// Keep arguments type-checked and considered used in player builds while the
// compile-time false branch guarantees that no logging call or argument work
// reaches the binary. This also keeps the release build warning-clean without
// scattering diagnostic-only casts throughout gameplay code.
#define LOGI(...) do { if constexpr (false) { __android_log_print(ANDROID_LOG_INFO, SAVR_TAG, __VA_ARGS__); } } while (false)
#define LOGW(...) do { if constexpr (false) { __android_log_print(ANDROID_LOG_WARN, SAVR_TAG, __VA_ARGS__); } } while (false)
#endif
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, SAVR_TAG, __VA_ARGS__)
