/*
  Written with Claude (Anthropic's AI assistant); run, tested and debugged on real hardware by Damian Delgado Ayon.

  Phase 1 - DC Motor Speed/Direction Control (DRV8871 driver)
  Custom PCB Motor Control & Validation Platform

  Hardware:
    Arduino Uno R3
    DRV8871 motor driver breakout
    Bemonoc 25GA370H 12V DC gear motor (encoder wired but not used yet)
    12V external power supply for the motor

  Wiring:
    Arduino D9  -> DRV8871 IN1
    Arduino D10 -> DRV8871 IN2
    Arduino GND -> DRV8871 GND  (shared ground - required)
    12V supply+ -> DRV8871 VM
    12V supply- -> DRV8871 GND
    Motor Red   -> DRV8871 OUT1
    Motor Black -> DRV8871 OUT2

  Serial usage (open Serial Monitor, 9600 baud, "Newline" line ending):
    Type an integer from -255 to 255 and press Enter.
      Positive = forward, negative = reverse, magnitude = speed (PWM duty).
      0 = stop.

  Example:
    200   -> spin forward at ~78% duty
    -150  -> spin reverse at ~59% duty
    0     -> stop
*/

const int IN1 = 9;
const int IN2 = 10;

void setup() {
  Serial.begin(9600);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  stopMotor();

  Serial.println("Motor controller ready.");
  Serial.println("Enter a speed from -255 to 255 (0 = stop):");
}

void loop() {
  if (Serial.available() > 0) {
    int command = Serial.parseInt();

    // parseInt() also consumes the trailing newline; clear any stray chars
    while (Serial.available() > 0) {
      Serial.read();
    }

    command = constrain(command, -255, 255);
    setMotor(command);

    Serial.print("Speed set to: ");
    Serial.println(command);
  }
}

// speed: -255 (full reverse) to 255 (full forward)
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
