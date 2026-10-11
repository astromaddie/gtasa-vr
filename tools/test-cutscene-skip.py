"""Compile the production cinematic skip path; check its input/symbol wiring."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "cutscene-skip-tests"
OUT.mkdir(parents=True, exist_ok=True)
main = (ROOT / "native/src/main.cpp").read_text()
start = main.index("static savr::cutsceneskip::Button cutsceneSkipButton;")
frame = main[start:main.index("#else", start)]
for gate in ("in.menu", "in.view", "in.grip[0] >= 0.25f", "in.grip[1] >= 0.25f",
             "menuWasOpen", "anyMenu", "vrcam::IsMobileMenuOpen()"):
    assert gate in frame, gate
assert "Update(in.a, xrFocused, skipBlocked," in frame
assert "const bool xrFocused = xr::IsSessionFocused();" in main
assert "constexpr bool skipCross = false;" in frame
assert "#include \"CutsceneSkip.h\"" in main
camera = (ROOT / "native/src/VrCamera.cpp").read_text()
assert "return cutsceneskip::FilterNativeInput(g_origCutsceneSkipInput," in camera
assert "0xa9be7bfdu, 0xf9000bf3u, 0x910003fdu, 0xf0002608u" in camera
assert "t[3]=0x580000a8u" in camera
assert "SetNativeInputFilterInstalled(g_origCutsceneSkipInput != nullptr)" in camera
symbols = (ROOT / "native/src/Symbols.cpp").read_text()
for native, field in (
    ("_ZN12CCutsceneMgr12SkipCutsceneEv", "CCutsceneMgr_Skip"),
    ("_ZN12CCutsceneMgr32IsCutsceneSkipButtonBeingPressedEv", "CCutsceneMgr_SkipButton"),
    ("_ZN12CCutsceneMgr19HasCutsceneFinishedEv", "CCutsceneMgr_HasFinished"),
    ("_ZN12CCutsceneMgr21ms_cutsceneLoadStatusE", "CCutsceneMgr_ms_loadStatus"),
    ("_ZN12CCutsceneMgr21ms_cutscenePlayStatusE", "CCutsceneMgr_ms_playStatus"),
    ("_ZN12CCutsceneMgr16ms_cutsceneTimerE", "CCutsceneMgr_ms_timer"),
):
    assert re.search(re.escape(native) + r'.*?&g\.' + field + r'\)', symbols), field
subprocess.run([
    "c++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
    "-I", str(ROOT / "native/src"),
    str(ROOT / "native/tests/cutscene_skip_test.cpp"),
    str(ROOT / "native/src/CutsceneSkip.cpp"), "-o", str(OUT / "test"),
], check=True)
subprocess.run([str(OUT / "test")], check=True)

# Exercise the actual trampoline builder with allocated host buffers and fake
# page permission calls. This checks the new ADRP relocation, continuation and
# untouched existing/default and boat-relocation paths without executing ARM.
builder = camera[camera.index("void* InstallTrampoline("):camera.index("#ifdef SAVR_DEV", camera.index("void* InstallTrampoline("))]
source = r'''
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#define LOGE(...) ((void)0)
#define CHECK(e) do { if (!(e)) { std::fprintf(stderr,"FAIL %d: %s\n",__LINE__,#e); std::exit(1); } } while(0)
constexpr int PROT_READ=1, PROT_WRITE=2, PROT_EXEC=4, MAP_PRIVATE=2, MAP_ANONYMOUS=0x20, _SC_PAGESIZE=1;
void* const MAP_FAILED=reinterpret_cast<void*>(-1);
alignas(4096) std::uint32_t storage[1024]{};
long sysconf(int) { return 4096; }
void* mmap(void*, unsigned long, int, int, int, int) { return storage; }
int mprotect(void*, unsigned long, int) { return 0; }
''' + builder + r'''
int main() {
    alignas(4096) std::uint32_t target[1024]{};
    const std::uint32_t original[]{0xa9be7bfd,0xf9000bf3,0x910003fd,0xf0002608};
    for (int route=0; route<3; ++route) {
        std::memcpy(target,original,16);
        const std::uintptr_t got=0x12345000;
        auto* t=static_cast<std::uint32_t*>(InstallTrampoline(target, target+100,
                                route==1?got:0,route==2?got:0));
        CHECK(t==storage);
        CHECK(t[4]==0x58000051 && t[5]==0xd61f0220);
        CHECK(*reinterpret_cast<void**>(t+6)==reinterpret_cast<char*>(target)+16);
        CHECK(target[0]==0x58000051 && target[1]==0xd61f0220);
        CHECK(*reinterpret_cast<void**>(target+2)==target+100);
        if(route==0) CHECK(!std::memcmp(t,original,16));
        if(route==1) CHECK(t[0]==0x58000108 && t[1]==0x580000e9 && t[2]==original[2] && t[3]==original[3]);
        if(route==2) {
            CHECK(!std::memcmp(t,original,12));
            CHECK((t[3]&0xff00001f)==0x58000008); // LDR literal X8
            const unsigned destination=12+((t[3]>>5)&0x7ffff)*4;
            CHECK(destination==32);
            CHECK(*reinterpret_cast<std::uintptr_t*>(reinterpret_cast<char*>(t)+destination)==got);
        }
        if(route) CHECK(*reinterpret_cast<std::uintptr_t*>(t+8)==got);
    }
    std::puts("PASS: production ARM trampoline builder, skip ADRP literal/continuation, unchanged default and boat relocation");
}
'''
(OUT / "trampoline.cpp").write_text(source)
subprocess.run(["c++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                str(OUT / "trampoline.cpp"), "-o", str(OUT / "trampoline")], check=True)
subprocess.run([str(OUT / "trampoline")], check=True)

# The cached image contains the cue. Exercise the production copy decision
# through initial appearance, changing progress, release, hide and retry.
xr = (ROOT / "native/src/Xr.cpp").read_text()
cache_gate = re.search(r"const bool skipCueNeedsCopy = ([^;]+);", xr)[1]
cache_source = "#include <cassert>\nint main(){ bool cachedProjectionHasSkipCue=false; "
cache_source += "auto copy=[&](bool skipCuePublished,bool success=true){ const bool needs=" + cache_gate + "; if(needs && success) cachedProjectionHasSkipCue=skipCuePublished; return needs; };"
cache_source += "assert(!copy(false)); assert(copy(true)); assert(copy(true)); assert(copy(true)); assert(copy(false,false)); assert(copy(false)); assert(!copy(false)); }"
(OUT / "cache.cpp").write_text(cache_source)
subprocess.run(["c++", "-std=c++20", "-Wall", "-Wextra", "-Werror", str(OUT / "cache.cpp"), "-o", str(OUT / "cache")], check=True)
subprocess.run([str(OUT / "cache")], check=True)
assert "if (!skipCueNeedsCopy && submitProjection && selectedStereoRepeat &&" in xr
assert "if (projectionReady) cachedProjectionHasSkipCue = skipCuePublished;" in xr
start = xr.index("void DrawCutsceneSkipOverlay(int width", xr.index("bool BuildCinemaOverlayProgram()"))
overlay = xr[start:xr.index("void DrawCinemaOverlay", start)]
for gate in ("progress < 0.0f", "!IsSessionFocused()", "IsMenuVisible()", "s.input.menu", "s.input.view", "s.input.grip[0]", "s.input.grip[1]"):
    assert gate in overlay, gate
assert "if (!s.input.a) progress = 0.0f;" in overlay
assert overlay.index("} saved;") < overlay.index("if (!BuildCinemaOverlayProgram()) return;")
for restore in ("glUseProgram(program)", "glBindVertexArray(vao)", "glActiveTexture(active)", "glBindTexture(GL_TEXTURE_2D, texture)", "glBindSampler(0, sampler)", "glColorMask(mask[0], mask[1], mask[2], mask[3])", "glPixelStorei(GL_UNPACK_ALIGNMENT, unpack)", "enable(GL_DEPTH_TEST, depth)", "enable(GL_CULL_FACE, cull)", "enable(GL_SCISSOR_TEST, scissor)", "enable(GL_BLEND, blend)", "enable(GL_STENCIL_TEST, stencil)", "enable(GL_RASTERIZER_DISCARD, discard)", "glBlendEquationSeparate(eqRgb, eqAlpha)"):
    assert restore in overlay, restore
assert "xr::PublishCutsceneSkip(cutsceneSkipButton.Eligible(), cutsceneSkipButton.Progress());" in frame
print("PASS: production repeat-copy decision appearance/progress/release/hide/retry, overlay input gates and independent GL state restoration wiring")

for state in ("GL_STENCIL_TEST", "GL_RASTERIZER_DISCARD"):
    assert f"glIsEnabled({state})" in overlay, state
    assert f"glDisable({state})" in overlay, state
print("PASS: skip overlay saves, disables and restores inherited stencil/rasterizer-discard state")
