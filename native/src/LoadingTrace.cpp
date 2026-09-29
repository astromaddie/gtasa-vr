#include "LoadingTrace.h"
#include "OptionalAssetPaths.h"
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <dlfcn.h>
#include <signal.h>
#include <string>
#include <sys/syscall.h>
#include <thread>
#include <ucontext.h>
#include <unistd.h>

namespace savr::loadingtrace {
namespace {
struct Sample {
    std::atomic<int> tid{0};
    std::atomic<unsigned> sequence{0};
    std::array<std::atomic<unsigned long long>, 33> regs{};
};
static_assert(std::atomic<unsigned long long>::is_always_lock_free);
static_assert(std::atomic<unsigned>::is_always_lock_free);
static_assert(std::atomic<int>::is_always_lock_free);
std::array<Sample, 16> samples;
std::atomic<bool> started{false};
void Capture(int, siginfo_t*, void* rawContext) {
    const int savedErrno = errno;
    const int tid = static_cast<int>(syscall(SYS_gettid));
    for (auto& sample : samples) {
        if (sample.tid.load(std::memory_order_relaxed) != tid) continue;
        const auto& context = static_cast<ucontext_t*>(rawContext)->uc_mcontext;
        for (unsigned i = 0; i < 31; ++i)
            sample.regs[i].store(context.regs[i], std::memory_order_relaxed);
        sample.regs[31].store(context.sp, std::memory_order_relaxed);
        sample.regs[32].store(context.pc, std::memory_order_relaxed);
        sample.sequence.fetch_add(1, std::memory_order_release);
        break;
    }
    errno = savedErrno;
}
void Address(FILE* log, const char* label, unsigned long long address) {
    Dl_info info{};
    if (dladdr(reinterpret_cast<void*>(address), &info)) {
        std::fprintf(log, "%s=%llx %s+%llx %s\n", label, address,
            info.dli_fname ? info.dli_fname : "?",
            address - reinterpret_cast<unsigned long long>(info.dli_fbase),
            info.dli_sname ? info.dli_sname : "?");
    } else std::fprintf(log, "%s=%llx\n", label, address);
}
void Run() {
    const auto path = std::string(modelsets::kFiles) + "vr_proper_loading_trace.txt";
    FILE* log = std::fopen(path.c_str(), "w");
    if (!log) return;
    struct sigaction previous{}, action{};
    sigaction(SIGURG, nullptr, &previous);
    if (previous.sa_handler != SIG_DFL && previous.sa_handler != SIG_IGN) {
        std::fprintf(log, "SIGURG already owned; no handler replaced\n");
        std::fclose(log); return;
    }
    action.sa_sigaction = Capture;
    action.sa_flags = SA_SIGINFO | SA_RESTART;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGURG, &action, nullptr)) {
        std::fprintf(log, "sigaction failed: %d\n", errno);
        std::fclose(log); return;
    }
    std::fprintf(log, "PC sampling only; no game state changes; pid=%d\n", getpid());
    std::fflush(log);
    for (unsigned round = 0; round < 12; ++round) {
        usleep(10000000);
        DIR* tasks = opendir("/proc/self/task");
        if (!tasks) break;
        std::fprintf(log, "round=%u\n", round);
        while (auto* entry = readdir(tasks)) {
            const int tid = std::atoi(entry->d_name);
            if (tid <= 0) continue;
            const auto commPath = std::string("/proc/self/task/") + entry->d_name + "/comm";
            char name[64]{};
            FILE* comm = std::fopen(commPath.c_str(), "r");
            if (!comm) continue;
            const bool read = std::fgets(name, sizeof(name), comm) != nullptr;
            std::fclose(comm);
            if (!read || (!std::strstr(name, "RenderQueue") && !std::strstr(name, "GameThread"))) continue;
            Sample* slot = nullptr;
            for (auto& sample : samples) if (sample.tid.load() == tid) { slot = &sample; break; }
            if (!slot) for (auto& sample : samples) if (!sample.tid.load()) {
                sample.tid.store(tid); slot = &sample; break;
            }
            if (!slot) continue;
            const auto before = slot->sequence.load(std::memory_order_acquire);
            if (syscall(SYS_tgkill, getpid(), tid, SIGURG)) continue;
            for (unsigned wait = 0; wait < 20 && slot->sequence.load(std::memory_order_acquire) == before; ++wait)
                usleep(1000);
            std::fprintf(log, "tid=%d %s", tid, name);
            if (slot->sequence.load(std::memory_order_acquire) == before) {
                std::fprintf(log, "sample pending\n"); continue;
            }
            Address(log, "pc", slot->regs[32].load());
            Address(log, "lr", slot->regs[30].load());
            for (unsigned i = 0; i < 32; ++i)
                std::fprintf(log, "x%u=%llx%c", i, slot->regs[i].load(), i % 4 == 3 ? '\n' : ' ');
        }
        closedir(tasks);
        std::fflush(log);
    }
    // SIGURG's prior default/ignored disposition is safe for a late sample.
    struct sigaction current{};
    if (!sigaction(SIGURG, nullptr, &current) && current.sa_sigaction == Capture)
        sigaction(SIGURG, &previous, nullptr);
    std::fprintf(log, "capture complete\n");
    std::fclose(log);
}
} // namespace
void Start() {
    const auto marker = std::string(modelsets::kFiles) + "vr_proper_loading_trace.enable";
    if (access(marker.c_str(), R_OK) || started.exchange(true)) return;
    std::thread(Run).detach();
}
} // namespace savr::loadingtrace
