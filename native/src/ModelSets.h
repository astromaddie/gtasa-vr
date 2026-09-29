#pragma once

namespace savr::modelsets {
enum Set { HD_WEAPONS, PROPER_FIXES, COUNT };
// Install before CGame starts reading asset databases. Choices latch for the
// whole process; toggling never mixes live map/streaming state from two packs.
void Install(void* gameHandle);
bool Enabled(int set);
void SetEnabled(int set, bool enabled);
bool Available(int set);
bool Applied(int set);
const char* Status(int set);
} // namespace savr::modelsets
