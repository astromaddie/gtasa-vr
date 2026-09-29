#pragma once

#include <cstdint>
#include <cstring>

namespace savr::cheats::directmission {

// Android 2.11.311: CRunningScript::Init @410e70 initializes through +12c;
// current IP is +20. ProcessCommands1000To1099 opcode 0417 dispatches to
// @424808, which loads the SCM mission and sets all mission ownership flags.
// The temporary parameter reader is never inserted into the script lists.
struct Api {
    void (*init)(void*){};
    int (*process)(void*, int){};
    bool (*onMission)(){};
    bool* running{};
    void** idleScripts{};
    std::uint16_t* missionCount{};
    std::uint16_t* exclusiveCount{};
    bool* missionPack{};
    int* area{};
    int* kingMarkerStage{};
    int* catalinaProgress{};

    bool Available() const {
        return init && process && onMission && running && idleScripts &&
               missionCount && exclusiveCount && missionPack && area && kingMarkerStage && catalinaProgress;
    }

    const char* BlockReason(bool inVehicle, bool debugLaunchPending) const {
        if (!Available()) return "LOADER UNAVAILABLE";
        if (*missionPack || *exclusiveCount || *missionCount <= 71)
            return "UNSUPPORTED MISSION PACK";
        if (onMission() || *running || debugLaunchPending)
            return "FINISH CURRENT MISSION";
        if (inVehicle) return "EXIT VEHICLE FIRST";
        if (*area != 0) return "GO OUTSIDE FIRST";
        if (!*idleScripts) return "NO FREE SCRIPT SLOT";
        return nullptr;
    }

    bool Launch(int number, bool inVehicle, bool debugLaunchPending) const {
        if (number < 0 || number > 1 || BlockReason(inVehicle, debugLaunchPending))
            return false;
        // 45 = CATCUT / King in Exile; 71 = DSKOOL / Back to School.
        // Verified against the mobile SCM mission-offset table, not menu IDs.
        unsigned char parameter[] = {0x04, static_cast<unsigned char>(number == 0 ? 45 : 71)};
        alignas(16) unsigned char reader[0x130]{};
        init(reader);
        unsigned char* ip = parameter;
        std::memcpy(reader + 0x20, &ip, sizeof(ip));
        process(reader, 0x0417);
        // The native CAT marker advances this caller-owned stage immediately
        // after opcode 0417 (mainV1.scm @73139). CATCUT itself only sets the
        // completion flag, so a direct launch must perform the same handoff.
        // Direct King selection skips the earlier First Date introduction.
        // CATCUT creates the cabin blip, but CAT with progress 0 still checks
        // Dillimore. Prepare the minimum cabin stage without completing any
        // robbery, changing CATCUT's success flag, or rewinding later dates.
        if (number == 0 && *running) {
            *kingMarkerStage = 2;
            if (*catalinaProgress == 0) *catalinaProgress = 1;
        }
        // Retail sets this synchronously when its new mission thread is ready.
        return *running;
    }
};

} // namespace savr::cheats::directmission
