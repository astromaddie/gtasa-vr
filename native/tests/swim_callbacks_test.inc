// Included after the production callbacks by tools/test-swimming.py.
namespace savr::swimming {
int RunCallbacks() {
    using namespace motion;
    int checks=0,failed=0;
    const auto check=[&](bool value,const char* label) {
        ++checks;
        if (!value) { ++failed; std::fprintf(stderr,"FAIL: %s\n",label); }
    };
    alignas(16) char ped[0x800]{},npc[0x800]{},task[0x100]{},pad[0x200]{},data[0x100]{};
    fakePed=ped; fakePad=pad;
    Write(ped,0x540,static_cast<void*>(data));
    Write(data,0x58,250.0f);
    Write(ped,0x8,Vec{0,0,-0.55f});
    Write(task,0x10,std::uint8_t{1}); Write(task,0x11,std::uint8_t{1});
    g_installed=true;
    g_water=[](float,float,float,float* z,bool,Vec*) { *z=0; return true; };
    g_maxBreath=[](int ability) { return ability==8?500.0f:0.0f; };
    g_control=[](void*,void*) { ++nativeControls; };
    g_resistance=[](void* t,void* p) {
        ++nativeResistance;
        Write(p,0x68,Vec{0.3f,0.4f,0.1f}); // stock swimming/auto-buoyancy
        Write(t,0x12,std::uint16_t{0}); // stock automatic surface transition
    };
    g.CTimer_ms_fTimeStep=&fakeStep;
    UpdateInput(true);
    check(xr::breath==0.5f,"breath gauge reads actual player data and lung capacity");
    check(g_enabled,"local player with swim task activates physical swimming");
    vrcam::eyeZ=-0.2f;
    OnControl(task,ped);
    check(Read<std::uint16_t>(task,0x12)==4,"submerged eye sets underwater before retail breath call");
    OnResistance(task,ped);
    const auto idle=Read<Vec>(ped,0x68);
    check(idle.z<0&&idle.x==0&&idle.y==0,"idle defeats native float/run velocity");
    check(Read<std::uint16_t>(task,0x12)==4,"native resistance cannot reset submerged state");
    check(nativeControls==1&&nativeResistance==1,"native animation and effects path still executes");

    vrcam::eyeZ=0.2f;
    OnControl(task,ped);
    check(Read<std::uint16_t>(task,0x12)<3,"surfaced eye restores native air recovery state");
    g_impulse={0,1,0};
    OnResistance(task,ped);
    check(Read<Vec>(ped,0x68).y>0,"stroke impulse reaches native moveSpeed");
    check(Length(g_impulse)==0,"impulse consumed exactly once");

    // The player can be driven by the task's ProcessControlAI during scripted
    // swim sections. With no control callback this frame, do not replace it.
    UpdateInput(true); OnResistance(task,ped);
    check(Read<Vec>(ped,0x68).z==0.1f,"scripted AI swim retains native physics");
    Write(task,0x12,std::uint16_t{5});
    UpdateInput(true); OnControl(task,ped); OnResistance(task,ped);
    check(Read<Vec>(ped,0x68).z==0.1f,"native jump-out and climbing retain velocity");
    OnControl(task,npc); OnResistance(task,npc);
    check(Read<Vec>(npc,0x68).z==0.1f,"NPC swimming untouched");

    // A near-surface climb faces the tracked boat, not a stale ped heading.
    g_setOrientation=[](void* p,float,float,float yaw) { Write(p,0x6c4,yaw); };
    g_control=[](void* t,void*) {
        if (missioncontrols::climb&&Read<std::uint16_t>(t,0x12)<=2)
            Write(t,0x12,std::uint16_t{5});
    };
    Write(task,0x12,std::uint16_t{4}); UpdateInput(true);
    g_direction={1,0,0}; missioncontrols::climb=true;
    OnControl(task,ped);
    check(Read<std::uint16_t>(task,0x12)==5,"near-surface water enter starts native climb despite eye submersion");
    check(std::abs(Read<float>(ped,0x6c8)+1.5707963f)<0.001f,
          "boat climb points CJ towards headset gaze");
    OnResistance(task,ped);
    check(Read<Vec>(ped,0x68).z==0.1f,"boat climb launch is not overwritten by swim drag");
    Write(ped,0x8,Vec{0,0,-5}); Write(task,0x12,std::uint16_t{4});
    UpdateInput(true); OnControl(task,ped);
    check(Read<std::uint16_t>(task,0x12)==4,"deep water cannot launch a boat climb");
    Write(ped,0x8,Vec{0,0,-0.55f}); missioncontrols::climb=false;

    g_impulse={1,1,1}; g_support=1;
    UpdateInput(false);
    check(!g_enabled&&Length(g_impulse)==0&&g_support==0,"menu/theater clears pending motion");
    check(xr::breath<0,"breath HUD hidden outside playable water context");
    UpdateInput(true); g_sampleTime-=1;
    check(!Controlled(ped),"stale input cannot override native physics");
    Write(pad,0x110,std::uint16_t{1}); UpdateInput(true);
    check(!g_enabled,"script-disabled player controls bypass physical swimming");
    Write(pad,0x110,std::uint16_t{0});
    locomotion::enabled=false; UpdateInput(true);
    check(!g_enabled&&xr::breath==0.5f,"toggle off restores retail but retains breath display");
    locomotion::enabled=true; missioncontrols::swim=false; UpdateInput(true);
    check(!g_enabled&&xr::breath<0,"leaving the water resets simulation and gauge");
    missioncontrols::swim=true; xr::headValid=false; UpdateInput(true);
    check(!g_enabled,"head tracking unavailable falls back to retail swimming");
    std::printf("%s: %d production swimming callback checks\n",failed?"FAIL":"PASS",checks);
    return failed?1:0;
}
}
int main() { return savr::swimming::RunCallbacks(); }
