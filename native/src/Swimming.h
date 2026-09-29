#pragma once

namespace savr::swimming {
void Install(void* gameHandle);
// Always called by the pad hook, including menu/theater frames, to clear
// tracking history and pending forces when gameplay input is unavailable.
void UpdateInput(bool enabled);
} // namespace savr::swimming
