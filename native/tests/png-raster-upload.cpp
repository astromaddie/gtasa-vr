#include "PngRasterUpload.h"
#include <vector>
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cstddef>
struct Image { int flags=0,w,h,depth=32; std::vector<unsigned char> pixels; Image(int x,int y):w(x),h(y),pixels(x*y*3,0x42){} };
struct Raster { char prefix[24]{}; int w,h; std::vector<unsigned char> storage; Raster(int x,int y,int capacity):w(x),h(y),storage(capacity,0xCD){} };
static_assert(offsetof(Image,w)==4 && offsetof(Image,h)==8 && offsetof(Raster,w)==0x18);
int copies=0,resamples=0,destroys=0;bool fail=false,badSize=false,failCopy=false;
void* NativeCopy(void* r,void* i) { ++copies;auto& dst=*static_cast<Raster*>(r);auto& src=*static_cast<Image*>(i);for(int y=0;y<src.h;++y)std::memcpy(dst.storage.data()+y*dst.w*3,src.pixels.data()+y*src.w*3,src.w*3);return failCopy?nullptr:r; }
void* Resample(const void* i,int w,int h) {++resamples;if(fail)return nullptr;const auto& src=*static_cast<const Image*>(i);auto* out=new Image(w+(badSize?1:0),h);for(int y=0;y<h;++y)for(int x=0;x<w;++x)for(int c=0;c<3;++c)out->pixels[(y*w+x)*3+c]=src.pixels[((y*src.h/h)*src.w+x*src.w/w)*3+c];return out;}
int Destroy(void* i){++destroys;delete static_cast<Image*>(i);return 1;}
bool Guard(const Raster& r){return std::all_of(r.storage.begin()+r.w*r.h*3,r.storage.end(),[](unsigned char x){return x==0xCD;});}
int main(int argc,char** argv){
 Image source(128,28);if(argc>1){FILE* f=fopen(argv[1],"rb");assert(f);assert(fread(source.pixels.data(),1,source.pixels.size(),f)==source.pixels.size());fclose(f);}
 Raster old(128,16,128*28*3+32);NativeCopy(&old,&source);assert(!Guard(old));puts("REPRODUCED: old 128x28 RGB upload overruns 128x16 raster by 4608 bytes");
 Raster fixed(128,16,128*28*3+32);auto original=source.pixels;assert(savr::hdweapons::pngupload::Copy(&fixed,&source,NativeCopy,Resample,Destroy)==&fixed);assert(Guard(fixed));assert(source.pixels==original);assert(resamples==1 && destroys==1);
 int n=1;
 for(auto dimensions : {std::pair{96,96},std::pair{127,31},std::pair{512,1},std::pair{1,28},std::pair{128,128},std::pair{300,512}}){int w=1,h=1;while(w*2<=dimensions.first)w*=2;while(h*2<=dimensions.second)h*=2;Image src(dimensions.first,dimensions.second);Raster dst(w,h,dimensions.first*dimensions.second*3+64);assert(savr::hdweapons::pngupload::Copy(&dst,&src,NativeCopy,Resample,Destroy)==&dst);assert(Guard(dst));++n;}
 int before=copies;fail=true;assert(!savr::hdweapons::pngupload::Copy(&fixed,&source,NativeCopy,Resample,Destroy));assert(copies==before && Guard(fixed));fail=false;
 badSize=true;int freed=destroys;assert(!savr::hdweapons::pngupload::Copy(&fixed,&source,NativeCopy,Resample,Destroy));assert(copies==before && destroys==freed+1);badSize=false;
 failCopy=true;freed=destroys;assert(!savr::hdweapons::pngupload::Copy(&fixed,&source,NativeCopy,Resample,Destroy));assert(destroys==freed+1 && Guard(fixed));
 assert(!savr::hdweapons::pngupload::Copy(nullptr,&source,NativeCopy,Resample,Destroy));fixed.h=0;assert(!savr::hdweapons::pngupload::Copy(&fixed,&source,NativeCopy,Resample,Destroy));
 printf("PASS: %d raster sizes, allocation/copy failures, ownership and guard bytes\n",n);
}
