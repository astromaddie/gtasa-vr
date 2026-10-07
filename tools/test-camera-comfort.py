#!/usr/bin/env python3
"""Run the actual Frame comfort adapter with only its device file path replaced."""
from pathlib import Path
import os, subprocess, tempfile
R = Path(__file__).resolve().parents[1]
source = (R / 'native/src/CameraComfort.cpp').read_text()
source = source.replace('#include "StoragePaths.h"', '#include <string>\nnamespace savr::storage { std::string Files(const char* leaf) { return leaf; } }')
harness = r"""
#include <fstream>
#include <iterator>
#include <cstdlib>
#define CHECK(e) do { if (!(e)) { std::fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #e); std::exit(1); } } while (0)
namespace savr::locomotion { bool resetPersonal=false; void ResetComfortDefaults(bool personal) { resetPersonal=personal; } }
using namespace savr::comfort;
int main(int argc, char**) {
 if (argc>1) {
  std::ofstream f("vr_camera.ini");
  f << "defaults_profile=frame_personal\nworld_scale=2\ncamera_closer=-0.4\ncamera_lower=-0.3\nheight_offset=0.2\nsettings_page_side=left\ncustom_option=keep\n";
 }
 CHECK(UnitsPerMeter()==(argc>1?2.f:1.f));
 CHECK(PersonalDefaults()==(argc>1));
 if (argc>1) {
  CHECK(std::abs(Closer()+.4f)<.001f && std::abs(Lower()+.3f)<.001f);
  CHECK(PanelSide()==1 && std::abs(HeightMeters(1.6f)-.2f)<.001f);
 }
 Defaults(); CHECK(savr::locomotion::resetPersonal==(argc>1));
 CHECK(Closer()==0 && Lower()==0 && UnitsPerMeter()==1 && PanelSide()==0);
 CalibrateStanding(1.8f); Adjust(5,1);
 CHECK(std::abs(HeightMeters(1.2f)-.6f)<.001f);
 CalibrateStanding(0.f); CHECK(std::abs(HeightMeters(1.2f)-.6f)<.001f);
 Adjust(5,1); CHECK(HeightMeters(1.2f)==0);
 SetEligible(true,false);
 float stick[2]={1,1}; ProcessInput(stick,true,false,false,true,1.0);
 CHECK(stick[0]==0 && stick[1]==0);
 stick[0]=stick[1]=1; ProcessInput(stick,true,false,false,true,1.02);
 CHECK(UnitsPerMeter()<1 && Closer()<0 && Lower()<0);
 const float scale=UnitsPerMeter(), close=Closer(), low=Lower();
 stick[0]=1;stick[1]=1; ProcessInput(stick,false,false,false,true,1.04);
 CHECK(stick[0]==0 && stick[1]==0 && UnitsPerMeter()==scale);
 stick[0]=stick[1]=0; ProcessInput(stick,false,false,false,true,1.06);
 stick[0]=1; ProcessInput(stick,false,false,false,true,1.08); CHECK(stick[0]==1);
 stick[0]=stick[1]=1; ProcessInput(stick,true,true,false,true,1.1);
 CHECK(UnitsPerMeter()==scale); // Menu wins over the modifier.
 stick[0]=stick[1]=1; ProcessInput(stick,true,false,false,false,1.2);
 CHECK(stick[0]==0 && stick[1]==0 && UnitsPerMeter()==scale);
 stick[0]=stick[1]=1; ProcessInput(stick,true,false,false,true,1.22);
 CHECK(UnitsPerMeter()==scale); // Held input cannot resume on focus gain.
 stick[0]=stick[1]=0; ProcessInput(stick,false,false,false,true,1.24);
 stick[0]=stick[1]=0; ProcessInput(stick,false,false,false,true,1.25);
 SetEligible(false,false);
 stick[0]=stick[1]=1; ProcessInput(stick,true,false,false,true,1.26);
 CHECK(UnitsPerMeter()==scale && stick[0]==1); // Occupied first-person grip is untouched.
 SetEligible(false,true);
 stick[0]=stick[1]=1; ProcessInput(stick,true,false,false,true,1.28);
 stick[0]=stick[1]=1; ProcessInput(stick,true,false,false,true,1.30);
 CHECK(UnitsPerMeter()<scale && Closer()==close && Lower()==low); // FP preview changes only scale.
 Adjust(6,1); Adjust(1,-1); Adjust(2,-1);
 std::ifstream f("vr_camera.ini"); const std::string saved((std::istreambuf_iterator<char>(f)),{});
 CHECK(saved.find("settings_page_side=left")!=std::string::npos);
 CHECK(saved.find(argc>1?"defaults_profile=frame_personal":"defaults_profile=standard")!=std::string::npos);
 if(argc>1) CHECK(saved.find("custom_option=keep")!=std::string::npos);
 std::puts("PASS: production Frame comfort defaults/saved values, seated calibration, inverse scale, signed adjustment, release/focus latch, Menu priority, FP contexts, and persistence");
}
"""
with tempfile.TemporaryDirectory(prefix='savr-camera-') as name:
 d=Path(name); cpp=d/'test.cpp'; cpp.write_text(source+harness)
 compiler=os.environ.get('CXX','c++')
 subprocess.run([compiler,'-std=c++20','-DSAVR_STEAM_FRAME','-I',str(R/'native/src'),'-I',str(R/'native/vendor/sfvr/include'),str(cpp),'-x','c++',str(R/'native/vendor/sfvr/src/sfvr_adjust.c'),'-o',str(d/'test')],check=True)
 for saved in (False,True):
  run=d/('saved' if saved else 'fresh'); run.mkdir()
  subprocess.run([str(d/'test')]+(['saved'] if saved else []),cwd=run,check=True)
