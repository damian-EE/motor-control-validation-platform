/*
  Written with Claude (Anthropic's AI assistant); run, tested and debugged on real hardware by Damian Delgado Ayon.

  Phase 3 v2 - Motor Control + Encoder RPM + INA219 (averaged current/voltage)
  Custom PCB Motor Control & Validation Platform

  What changed from Phase 3:
    The motor is driven by PWM, so the current drawn from the supply is
    chopped on and off ~490 times per second. A single INA219 reading can
    land in either phase, which made the printed current jump around.
    This version takes as many readings as it can during each 500 ms
    window and prints their AVERAGE.

  Output (every 500 ms):  time_ms,pwm,rpm,current_mA,voltage_V
  Serial: 9600 baud. Type a speed from -255 to 255 (0 = stop).

  Requires: Adafruit_INA219 library

  Hardware:
    12V supply+ -> INA219 VIN+
    INA219 VIN- -> DRV8871 VM
    DRV8871 IN1 -> D9, IN2 -> D10
    Encoder A -> D2
    INA219 VCC -> 5V, GND -> GND, SDA -> A4, SCL -> A5
*/

#include <Wire.h>
#include <Adafruit_INA219.h>

Adafruit_INA219 ina219;

const int IN1 = 9;
const int IN2 = 10;
const int ENCODER_A = 2;

const long PULSES_PER_REV = 540;
const unsigned long RPM_INTERVAL_MS = 500;

volatile unsigned long pulseCount = 0;
unsigned long lastRpmCalcTime = 0;
int currentCommand = 0;

// Running sums for averaging the INA219 readings within one interval
float currentSum_mA = 0;
float voltageSum_V = 0;
unsigned long sampleCount = 0;

void setup() {
  Serial.begin(9600);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(ENCODER_A, INPUT_PULLUP);

  attachInterrupt(digitalPinToInterrupt(ENCODER_A), onEncoderPulse, RISING);

  if (!ina219.begin()) {
    Serial.println("Failed to find INA219 chip - check wiring (SDA/SCL/VCC/GND)");
    while (1) { delay(10); }
  }
  Wire.setClock(400000);  // faster I2C = more samples per interval

  stopMotor();
  lastRpmCalcTime = millis();

  Serial.println("Motor controller ready (Phase 3 v2 - averaged sensing).");
  Serial.println("Enter a speed from -255 to 255 (0 = stop):");
  Serial.println("time_ms,pwm,rpm,current_mA,voltage_V");
}

void loop() {
  if (Serial.available() > 0) {
    int command = Serial.parseInt();
    while (Serial.available() > 0) {
      Serial.read();
    }
    currentCommand = constrain(command, -255, 255);
    setMotor(currentCommand);
  }

  // Take a reading every pass through loop() and add it to the running sum
  currentSum_mA += ina219.getCurrent_mA();
  voltageSum_V += ina219.getBusVoltage_V();
  sampleCount++;

  unsigned long now = millis();
  if (now - lastRpmCalcTime >= RPM_INTERVAL_MS) {
    noInterrupts();
    unsigned long counted = pulseCount;
    pulseCount = 0;
    interrupts();

    float elapsedSeconds = (now - lastRpmCalcTime) / 1000.0;
    float rpm = (counted / elapsedSeconds) / PULSES_PER_REV * 60.0;

    float current_mA = 0;
    float busVoltage = 0;
    if (sampleCount > 0) {
      current_mA = currentSum_mA / sampleCount;
      busVoltage = voltageSum_V / sampleCount;
    }

    Serial.print(now);
    Serial.print(",");
    Serial.print(currentCommand);
    Serial.print(",");
    Serial.print(rpm, 1);
    Serial.print(",");
    Serial.print(current_mA, 1);
    Serial.print(",");
    Serial.println(busVoltage, 2);

    currentSum_mA = 0;
    voltageSum_V = 0;
    sampleCount = 0;
    lastRpmCalcTime = now;
  }
}

void onEncoderPulse() {
  pulseCount++;
}

void setMotor(int speed) {
  if (speed > 0) {
    analogWrite(IN1, speed);
    analogWrite(IN2, 0);
  } else if (speed < 0) {
    analogWrite(IN1, 0);
    analogWrite(IN2, -speed);
  } else {
    stopMotor();
  }
}

void stopMotor() {
  analogWrite(IN1, 0);
  analogWrite(IN2, 0);
}
