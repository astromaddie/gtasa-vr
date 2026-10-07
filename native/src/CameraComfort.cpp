#include "CameraComfort.h"
#include "Locomotion.h"
#include "StoragePaths.h"
#include <sfvr/sfvr_adjust.h>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>
#include <unistd.h>

namespace savr::comfort {
namespace {
std::once_flag init;
std::mutex mutex;
std::atomic<float> scale{1}, closer{0}, lower{0}, height{0}, head{1}, standing{1.6f};
std::atomic<int> side{0};
std::atomic<bool> seated{false}, personal{false}, eligible{false}, preview{false};
sfvr_adjust_state input{};
sfvr_adjust_config config{};
bool dirty=false;
double changedAt=0;
std::vector<std::string> unknown;
const char* keys[]={"world_scale", "camera_closer", "camera_lower", "height_offset",
                   "head_translation", "seated", "settings_page_side", "defaults_profile", "standing_height"};
bool Known(const char* key) { for(auto k:keys) if(!std::strcmp(k,key))return true; return false; }
void Load() {
    sfvr_adjust_init(&input); sfvr_adjust_config_default(&config);
    config.world_scale_min=.25f; config.world_scale_max=4;
    auto path=storage::Files("vr_camera.ini");
    if(FILE* f=std::fopen(path.c_str(),"r")) {
        char line[256], key[64], word[64]; float value;
        while(std::fgets(line,sizeof(line),f)) {
            if(std::sscanf(line," %63[^= ] = %63s",key,word)==2) {
                if(!std::strcmp(key,"defaults_profile") && (!std::strcmp(word,"standard")||!std::strcmp(word,"frame_personal"))) {
                    personal=!std::strcmp(word,"frame_personal");continue;
                }
                if(!std::strcmp(key,"settings_page_side") && (!std::strcmp(word,"right")||!std::strcmp(word,"left")||!std::strcmp(word,"centre"))) {
                    side=!std::strcmp(word,"right")?0:!std::strcmp(word,"left")?1:2;continue;
                }
            }
            if(std::sscanf(line," %63[^= ] = %f",key,&value)==2 && std::isfinite(value)) {
                if(!std::strcmp(key,"world_scale"))scale=std::clamp(value,.25f,4.f);
                else if(!std::strcmp(key,"camera_closer"))closer=std::clamp(value,-1.f,.8f);
                else if(!std::strcmp(key,"camera_lower"))lower=std::clamp(value,-1.f,1.f);
                else if(!std::strcmp(key,"height_offset"))height=std::clamp(value,-1.f,1.f);
                else if(!std::strcmp(key,"head_translation"))head=std::clamp(value,0.f,2.f);
                else if(!std::strcmp(key,"seated"))seated=value!=0;
                else if(!std::strcmp(key,"settings_page_side"))side=std::clamp(int(value),0,2);
                else if(!std::strcmp(key,"defaults_profile"))personal=value!=0;
                else if(!std::strcmp(key,"standing_height"))standing=std::clamp(value,.5f,2.5f);
                else unknown.emplace_back(line);
            } else if(std::sscanf(line," %63[^= ]",key)!=1 || !Known(key)) unknown.emplace_back(line);
        }
        std::fclose(f);
    }
}
void Ready(){std::call_once(init,Load);}
void Save() {
    auto path=storage::Files("vr_camera.ini"), tmp=path+".tmp";
    if(FILE* f=std::fopen(tmp.c_str(),"w")) {
        for(auto& line:unknown)std::fputs(line.c_str(),f);
        std::fprintf(f,"world_scale=%.7g\ncamera_closer=%.7g\ncamera_lower=%.7g\nheight_offset=%.7g\nhead_translation=%.7g\nseated=%d\nsettings_page_side=%s\ndefaults_profile=%s\nstanding_height=%.7g\n",
            double(scale.load()),double(closer.load()),double(lower.load()),double(height.load()),double(head.load()),int(seated.load()),side==0?"right":side==1?"left":"centre",personal?"frame_personal":"standard",double(standing.load()));
        const bool ok=std::fflush(f)==0 && ::fsync(::fileno(f))==0;
        const bool closed=std::fclose(f)==0;
        if(ok&&closed&&std::rename(tmp.c_str(),path.c_str())==0)dirty=false;
    }
}
}
float UnitsPerMeter(){Ready();return scale;}
float Closer(){Ready();return closer;}
float Lower(){Ready();return lower;}
float HeadTranslation(){Ready();return head;}
float HeightMeters(float origin){Ready();return height+(seated?std::max(0.f,standing.load()-origin):0.f);}
int PanelSide(){Ready();return side;}
bool PersonalDefaults(){Ready();return personal;}
void CalibrateStanding(float meters){Ready();if(std::isfinite(meters)&&meters>=.5f&&meters<=2.5f){std::lock_guard<std::mutex> lock(mutex);standing=meters;dirty=true;Save();}}
void SetEligible(bool thirdPerson,bool settingsPreview){eligible=thirdPerson;preview=settingsPreview;}
void ProcessInput(float stick[2],bool grip,bool menu,bool view,bool focused,double time) {
    Ready();std::lock_guard<std::mutex> lock(mutex);
    if(!focused){sfvr_adjust_focus_lost(&input);stick[0]=stick[1]=0;if(dirty)Save();return;}
    float s=scale,c=closer,l=lower;
    const bool allowed=eligible||preview;
    sfvr_adjust_update(&input,&config,stick,grip,allowed,menu,view,time,&s,eligible?&c:nullptr,eligible?&l:nullptr);
    if(s!=scale||c!=closer||l!=lower){scale=s;closer=c;lower=l;dirty=true;changedAt=time;}
    if(dirty && time-changedAt>=.5)Save();
}
void Defaults(){
    Ready();{std::lock_guard<std::mutex> lock(mutex);scale=1;closer=lower=height=0;head=1;seated=false;side=0;dirty=true;Save();}
    locomotion::ResetComfortDefaults(personal);
}
void Adjust(int row,int direction){
    Ready();if(row==8){Defaults();return;}
    std::lock_guard<std::mutex> lock(mutex);const int d=direction<0?-1:1;
    switch(row){
    case 0:scale=std::clamp(scale.load()*std::pow(1.1f,float(-d)),.25f,4.f);break;
    case 1:closer=std::clamp(closer.load()+d*.05f,-1.f,.8f);break;
    case 2:lower=std::clamp(lower.load()+d*.05f,-1.f,1.f);break;
    case 3:height=std::clamp(height.load()+d*.05f,-1.f,1.f);break;
    case 4:head=std::clamp(head.load()+d*.1f,0.f,2.f);break;
    case 5:seated=!seated;break;
    case 6:side=(side.load()+d+3)%3;break;
    case 7:personal=!personal;break;
    default:return;
    }dirty=true;Save();
}
void RowText(int row,char* out,unsigned n){
    Ready();switch(row){
    case 0:std::snprintf(out,n,"WORLD SIZE   < %.0f%% >",100.f/scale.load());break;
    case 1:std::snprintf(out,n,"CLOSER / FARTHER   < %+.2f >",double(closer.load()));break;
    case 2:std::snprintf(out,n,"LOWER / HIGHER   < %+.2f >",double(lower.load()));break;
    case 3:std::snprintf(out,n,"HEIGHT   < %+.2f M >",double(height.load()));break;
    case 4:std::snprintf(out,n,"HEAD MOVEMENT   < %.1f X >",double(head.load()));break;
    case 5:std::snprintf(out,n,"SEATED   < %s >",seated?"ON":"OFF");break;
    case 6:std::snprintf(out,n,"PANEL   < %s >",side==0?"RIGHT":side==1?"LEFT":"CENTRE");break;
    case 7:std::snprintf(out,n,"DEFAULTS PROFILE   < %s >",personal?"FRAME PERSONAL":"STANDARD");break;
    case 8:std::snprintf(out,n,"DEFAULTS");break;
    default:std::snprintf(out,n,"BACK");break;
    }
}
}
