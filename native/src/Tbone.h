#pragma once
namespace savr::tbone {
void Install(void* handle);
void UpdateInput(bool enabled,bool a);
bool Active();
bool Ready();
bool ClaimsA();
bool WidgetReleased(bool original);
}
