/*
  I2C Scanner - finds every I2C device on the bus.
  Wiring: module SDA -> A4, SCL -> A5, VCC -> 5V, GND -> GND.
  Open the Serial Monitor at 9600 baud. It rescans every 3 seconds.
  The INA219 normally appears at 0x40.
*/

#include <Wire.h>

void setup() {
  Serial.begin(9600);
  Wire.begin();
  Serial.println("I2C scanner ready.");
}

void loop() {
  Serial.println("Scanning...");
  int found = 0;
  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    byte error = Wire.endTransmission();
    if (error == 0) {
      Serial.print("Found device at 0x");
      if (addr < 16) Serial.print("0");
      Serial.println(addr, HEX);
      found++;
    }
  }
  if (found == 0) {
    Serial.println("No I2C devices found");
  }
  Serial.println();
  delay(3000);
}
