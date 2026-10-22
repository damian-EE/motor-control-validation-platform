/*
  Written with Claude (Anthropic's AI assistant); run, tested and debugged on real hardware by Damian Delgado Ayon.

  Phase 2 - DC Motor Speed/Direction Control + Encoder RPM Measurement
  Custom PCB Motor Control & Validation Platform

  Adds to Phase 1:
    - Reads the motor's built-in Hall encoder (Yellow wire / A channel)
    - Calculates and prints RPM every 500ms

  Hardware (same as Phase 1, plus encoder wires):
    Arduino D9  -> DRV8871 IN1
    Arduino D10 -> DRV8871 IN2
    Arduino GND -> DRV8871 GND
    12V supply  -> DRV8871 VM / GND
    Motor Red/Black -> DRV8871 MOTOR terminal

    Motor Blue   -> Arduino 5V      (encoder power)
    Motor Green  -> Arduino GND     (encoder ground)
    Motor Yellow -> Arduino D2      (encoder A - counted)
    Motor White  -> Arduino D3      (encoder B - wired, unused for now)

  Encoder spec (Bemonoc 25GA370H): 540 pulses per output-shaft revolution.

  Serial usage (9600 baud, "Newline" line ending):
    Type an integer from -255 to 255 and press Enter to set motor speed.
    Every 500ms, the sketch prints: time_ms,pwm,rpm
*/

const int IN1 = 9;
const int IN2 = 10;
const int ENCODER_A = 2;

const long PULSES_PER_REV = 540;
const unsigned long RPM_INTERVAL_MS = 500;

volatile unsigned long pulseCount = 0;
unsigned long lastRpmCalcTime = 0;
int currentCommand = 0;

void setup() {
  Serial.begin(9600);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(ENCODER_A, INPUT_PULLUP);

  attachInterrupt(digitalPinToInterrupt(ENCODER_A), onEncoderPulse, RISING);

  stopMotor();
  lastRpmCalcTime = millis();

  Serial.println("Motor controller ready (Phase 2 - RPM measurement).");
  Serial.println("Enter a speed from -255 to 255 (0 = stop):");
  Serial.println("time_ms,pwm,rpm");
}

void loop() {
  // Handle incoming speed commands
  if (Serial.available() > 0) {
    int command = Serial.parseInt();
    while (Serial.available() > 0) {
      Serial.read();
    }
    currentCommand = constrain(command, -255, 255);
    setMotor(currentCommand);
  }

  // Print RPM every RPM_INTERVAL_MS
  unsigned long now = millis();
  if (now - lastRpmCalcTime >= RPM_INTERVAL_MS) {
    noInterrupts();
    unsigned long counted = pulseCount;
    pulseCount = 0;
    interrupts();

    float elapsedSeconds = (now - lastRpmCalcTime) / 1000.0;
    float rpm = (counted / elapsedSeconds) / PULSES_PER_REV * 60.0;

    Serial.print(now);
    Serial.print(",");
    Serial.print(currentCommand);
    Serial.print(",");
    Serial.println(rpm, 1);

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
