#pragma once
namespace savr::comfort {
// Native SA positions are in game units; XR and panel coordinates are metres.
float UnitsPerMeter();
float Closer();
float Lower();
float HeadTranslation();
float HeightMeters(float originHeightMeters);
int PanelSide();                 // 0 right, 1 left, 2 centre
bool PersonalDefaults();
void CalibrateStanding(float meters);
void SetEligible(bool thirdPerson, bool settingsPreview);
void ProcessInput(float rightStick[2], bool leftGrip, bool menu, bool view,
                  bool focused, double predictedDisplaySeconds);
void Adjust(int row, int direction);
void Defaults();
void RowText(int row, char* text, unsigned capacity);
constexpr int kRows = 10; // size, closer, lower, height, head, seated, panel, profile, defaults, back
}
