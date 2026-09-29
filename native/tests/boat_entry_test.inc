namespace savr::boatentry {
int RunTests() {
    int checked=0,failed=0;
    const auto check=[&](bool value,const char* message) {
        ++checked;
        if (!value) { ++failed; std::fprintf(stderr,"FAIL: %s\n",message); }
    };
    const auto write=[](void* p,int offset,const auto& value) {
        std::memcpy(static_cast<char*>(p)+offset,&value,sizeof(value));
    };
    write(boat,0x5a,std::uint8_t{2});
    g_vehicleHealthy=[](void*) { return vehicleHealthy; };
    g_pedHealthy=[](void*) { return pedHealthy; };
    g_canOpenLocks=[](void*,void*) { return unlocked; };
    void* intelligencePtr=intelligence;
    write(ped,0x538,intelligencePtr);
    g_taskAlloc=[](std::size_t size)->void* {
        return allocationOk&&size==sizeof(driveTask)?driveTask:nullptr;
    };
    g_driveCtor=[](void* task,void* v) { driveArgs=task==driveTask&&v==boat; };
    g_driveDelete=[](void* task) { if (task==driveTask) ++deletedTasks; };
    g_setTask=[](void* manager,void* task,int slot,bool force) {
        if (manager==intelligence+8&&task==driveTask&&slot==3&&!force&&driveArgs)
            ++driveCalls;
    };
    g_seatCtor=[](void* task,void* v,void* utility) {
        ctorArgs=v==boat&&utility==nullptr;
        std::memset(task,0,0x38);
    };
    g_seatDtor=[](void*) { ++seatDestructed; };
    g_seatProcess=[](void* task,void* p) {
        ++seatCalls;
        nativeArgsCorrect=p==ped&&ctorArgs&&static_cast<char*>(task)[0x30]==1;
        if (nativeSuccess) seated=boat;
        return nativeSuccess;
    };
    write(ped,0x8,Vec{0,0,0}); // bank, no swim task required
    check(TryEnter()&&seated==boat&&seatCalls==1&&nativeArgsCorrect,
          "bank entry targets a real hull and calls native driver seating once");
    seated=nullptr; write(ped,0x8,Vec{0,0,-0.7f});
    eye={0,0,0.02f}; point={0,1,-0.3f};
    check(TryEnter()&&seated==boat&&seatCalls==2,"water entry seats instead of jumping");
    check(driveCalls==2&&seatDestructed==2&&deletedTasks==0,
          "both seats use player CarDrive task and release native seat references");
    const int calls=seatCalls;
    check(!TryEnter()&&seatCalls==calls,"already seated preserves normal exit handling");
    seated=nullptr; write(ped,0x8,Vec{0,0,0}); eye={0,0,0.72f}; point={0,1,0};
    unlocked=false;
    check(TryEnter()&&seatCalls==calls,"locked boat consumes press without bypassing lock");
    unlocked=true; void* occupant=ped; write(boat,0x5a0,occupant);
    check(TryEnter()&&seatCalls==calls,"occupied boat never ejects its driver");
    occupant=nullptr; write(boat,0x5a0,occupant);
    vehicleHealthy=false;
    check(TryEnter()&&seatCalls==calls,"destroyed boat rejected");
    vehicleHealthy=true; pedHealthy=false;
    check(!TryEnter()&&seatCalls==calls,"dead or unhealthy player rejected");
    pedHealthy=true;
    write(pad,0x110,std::uint16_t{1});
    check(!TryEnter()&&seatCalls==calls,"script-disabled controls cannot board");
    write(pad,0x110,std::uint16_t{0}); write(pad,0x12d,std::uint8_t{1});
    check(!TryEnter()&&seatCalls==calls,"native entry-disabled gate respected");
    write(pad,0x12d,std::uint8_t{0});
    appearance=1;
    check(!TryEnter()&&seatCalls==calls,"ordinary cars retain existing entry path");
    appearance=4; collision=false;
    check(!TryEnter()&&seatCalls==calls,"no collision hit cannot select a boat");
    collision=true; write(boat,0x5a,std::uint8_t{1});
    check(!TryEnter()&&seatCalls==calls,"wall as first hit blocks boarding through it");
    write(boat,0x5a,std::uint8_t{2}); point={0,4,0};
    check(!TryEnter()&&seatCalls==calls,"distant hull outside reach rejected");
    point={0,0,-2};
    check(!TryEnter()&&seatCalls==calls,"hull too far below bank rejected");
    point={0,1,0}; eye={0,0,8};
    check(!TryEnter()&&seatCalls==calls,"stale or remote camera cannot extend reach");
    eye={0,0,0.72f}; headValid=false;
    check(!TryEnter()&&seatCalls==calls,"invalid tracked view cannot board");
    headValid=true; nativeSuccess=false;
    check(TryEnter()&&seatCalls==calls+1&&seated==nullptr,
          "native failure consumes edge instead of dispatching a second entry");
    check(deletedTasks==1&&driveCalls==2&&seatDestructed==3,
          "failed seat deletes allocated drive task without installing it");
    nativeSuccess=true; allocationOk=false;
    check(TryEnter()&&seatCalls==calls+1,"task pool failure cannot strand a seated player");
    allocationOk=true; intelligencePtr=nullptr; write(ped,0x538,intelligencePtr);
    check(TryEnter()&&seatCalls==calls+1,"missing task manager cannot seat player");
    intelligencePtr=intelligence; write(ped,0x538,intelligencePtr);
    appearance=1; write(boat,0x32,std::uint16_t{539});
    check(TryEnter()&&seated==boat&&driveCalls==3,"Vortex hovercraft uses nearby-hull boarding");
    seated=nullptr; write(boat,0x32,std::uint16_t{400});
    check(!TryEnter()&&driveCalls==3,"Vortex exception does not capture normal cars");
    std::printf("%s: %d production boat entry checks\n",failed?"FAIL":"PASS",checked);
    return failed?1:0;
}
}
int main() { return savr::boatentry::RunTests(); }
