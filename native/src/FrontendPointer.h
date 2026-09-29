#pragma once
#include <cmath>
namespace savr::frontendpointer {
enum class Action { None, Down, Move, Up, Cancel };
struct Event { Action action{Action::None}; float x{},y{}; };
struct State {
    bool touching{},dragging{},releaseRequired{};
    float downU{},downV{},downX{},downY{};
    Event Update(bool blocked,bool pressed,bool valid,float u,float v,float width,float height) {
        if (blocked) {
            releaseRequired=true;
            const bool cancel=touching;touching=false;dragging=false;
            return {cancel?Action::Cancel:Action::None,downX,downY};
        }
        if (releaseRequired) {
            if (!pressed) releaseRequired=false;
            return {};
        }
        const bool click=pressed && valid && std::isfinite(u) && std::isfinite(v);
        const float x=u*width,y=v*height;
        if (click && !touching) {
            touching=true;dragging=false;downU=u;downV=v;downX=x;downY=y;
            return {Action::Down,x,y};
        }
        if (click && touching) {
            if (std::abs(u-downU)+std::abs(v-downV)>0.09f) dragging=true;
            return dragging?Event{Action::Move,x,y}:Event{};
        }
        if (!click && touching) {
            touching=false;
            return dragging && valid?Event{Action::Up,x,y}:Event{Action::Up,downX,downY};
        }
        return {};
    }
};
}
