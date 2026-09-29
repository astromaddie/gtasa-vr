#pragma once

namespace savr::boatentry {
void Install(void* gameHandle);
// Called once on a permitted ENTER edge. Returns true when a close boat owns
// the press, including a locked/occupied boat; false preserves normal entry.
bool TryEnter();
}
