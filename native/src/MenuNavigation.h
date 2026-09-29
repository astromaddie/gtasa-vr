#pragma once

namespace savr::menu {
struct Directions { bool up{},down{}; };

// Match the Quest Vice City menu: vertical selection only. Values are edited
// by triggers/buttons, so horizontal stick drift cannot change a setting.
inline Directions Navigate(bool open,float /*xAxis*/,float yAxis,bool grips) {
    if (!open||grips) return {};
    return {yAxis>0.65f,yAxis<-0.65f};
}
} // namespace savr::menu
