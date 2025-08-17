import cv2
import mediapipe as mp
import pyautogui
import math
import time
import subprocess

def run_gesture_mouse():
    pyautogui.FAILSAFE = False  # ⚠ Disable for testing. Remove or set to True in production.
    
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )
    screen_width, screen_height = pyautogui.size()
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    CLICK_THRESHOLD = 0.05
    SCREENSHOT_THRESHOLD = 0.08
    TWO_HAND_ZOOM_SENSITIVITY = 0.15
    MOVE_THRESHOLD = 5
    DOUBLE_CLICK_DELAY = 0.4
    PAUSE_THRESHOLD = 0.07
    GESTURE_COOLDOWN = 1.5

    gesture_text = ""
    last_action_time = 0
    prev_zoom_distance = 0
    last_click_time = 0
    last_click_pos = None
    cursor_movement_enabled = True
    prev_scroll_y = None
    last_app_launch_time = 0
    app_launch_cooldown = 3.0
    click_count = 0

    while True:
        success, image = cap.read()
        if not success:
            continue

        image = cv2.flip(image, 1)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = hands.process(image_rgb)

        if time.time() - last_action_time > 1:
            gesture_text = ""

        current_time = time.time()
        can_perform_action = current_time - last_action_time > GESTURE_COOLDOWN
        can_launch_app = current_time - last_app_launch_time > app_launch_cooldown

        if results.multi_hand_landmarks:
            hand_count = len(results.multi_hand_landmarks)

            if hand_count == 2 and can_perform_action:
                hand1 = results.multi_hand_landmarks[0].landmark
                hand2 = results.multi_hand_landmarks[1].landmark
                h, w = image.shape[:2]
                
                hand1_pos = (int(hand1[8].x * w), int(hand1[8].y * h))
                hand2_pos = (int(hand2[8].x * w), int(hand2[8].y * h))
                current_distance = math.hypot(hand1_pos[0]-hand2_pos[0], hand1_pos[1]-hand2_pos[1])
                
                if prev_zoom_distance > 0:
                    if current_distance > prev_zoom_distance + (TWO_HAND_ZOOM_SENSITIVITY * w):
                        pyautogui.hotkey('ctrl', '+')
                        gesture_text = "ZOOM IN"
                        last_action_time = current_time
                    elif current_distance < prev_zoom_distance - (TWO_HAND_ZOOM_SENSITIVITY * w):
                        pyautogui.hotkey('ctrl', '-')
                        gesture_text = "ZOOM OUT"
                        last_action_time = current_time
                prev_zoom_distance = current_distance

            for hand_landmarks in results.multi_hand_landmarks:
                landmarks = hand_landmarks.landmark
                h, w = image.shape[:2]

                thumb_tip = [int(landmarks[4].x * w), int(landmarks[4].y * h)]
                index_tip = [int(landmarks[8].x * w), int(landmarks[8].y * h)]
                middle_tip = [int(landmarks[12].x * w), int(landmarks[12].y * h)]
                ring_tip = [int(landmarks[16].x * w), int(landmarks[16].y * h)]
                pinky_tip = [int(landmarks[20].x * w), int(landmarks[20].y * h)]
                wrist = [int(landmarks[0].x * w), int(landmarks[0].y * h)]

                cursor_x = int(landmarks[8].x * screen_width)
                cursor_y = int(landmarks[8].y * screen_height)

                cursor_x = max(10, min(screen_width - 10, cursor_x))
                cursor_y = max(10, min(screen_height - 10, cursor_y))

                if cursor_movement_enabled:
                    pyautogui.moveTo(cursor_x, cursor_y)

                thumb_index_dist = math.hypot(thumb_tip[0]-index_tip[0], thumb_tip[1]-index_tip[1])
                thumb_middle_dist = math.hypot(thumb_tip[0]-middle_tip[0], thumb_tip[1]-middle_tip[1])
                thumb_ring_dist = math.hypot(thumb_tip[0]-ring_tip[0], thumb_tip[1]-ring_tip[1])
                thumb_pinky_dist = math.hypot(thumb_tip[0]-pinky_tip[0], thumb_tip[1]-pinky_tip[1])

                thumb_up = landmarks[4].y < landmarks[3].y
                index_up = landmarks[8].y < landmarks[6].y
                middle_up = landmarks[12].y < landmarks[10].y
                ring_up = landmarks[16].y < landmarks[14].y
                pinky_up = landmarks[20].y < landmarks[18].y

                current_click_pos = (thumb_tip[0], thumb_tip[1])

                if thumb_index_dist < CLICK_THRESHOLD * w:
                    if (last_click_time > 0 and 
                        current_time - last_click_time < DOUBLE_CLICK_DELAY and
                        math.hypot(current_click_pos[0]-last_click_pos[0], current_click_pos[1]-last_click_pos[1]) < 50):
                        click_count += 1
                        if click_count == 2:
                            try:
                                pyautogui.doubleClick()
                                gesture_text = "DOUBLE CLICK"
                            except pyautogui.FailSafeException:
                                print("Fail-safe triggered during double click.")
                            click_count = 0
                    else:
                        click_count = 1
                        pyautogui.click()
                        gesture_text = "LEFT CLICK"

                    last_click_time = current_time
                    last_click_pos = current_click_pos
                    last_action_time = current_time

                elif thumb_middle_dist < CLICK_THRESHOLD * w and can_perform_action:
                    pyautogui.rightClick()
                    gesture_text = "RIGHT CLICK"
                    last_action_time = current_time
                    click_count = 0

                elif thumb_pinky_dist < SCREENSHOT_THRESHOLD * w and can_perform_action:
                    pyautogui.screenshot(f"screenshot_{int(time.time())}.png")
                    gesture_text = "SCREENSHOT TAKEN"
                    last_action_time = current_time
                    click_count = 0

                elif thumb_ring_dist < PAUSE_THRESHOLD * w and can_perform_action:
                    cursor_movement_enabled = not cursor_movement_enabled
                    gesture_text = "CURSOR " + ("PAUSED" if not cursor_movement_enabled else "RESUMED")
                    last_action_time = current_time
                    click_count = 0

                elif index_up and middle_up and not ring_up and not pinky_up:
                    wrist_y = wrist[1]
                    if prev_scroll_y is not None:
                        scroll_direction = wrist_y - prev_scroll_y
                        if abs(scroll_direction) > 20:
                            pyautogui.scroll(40 if scroll_direction < 0 else -40)
                            gesture_text = "SCROLL " + ("UP" if scroll_direction < 0 else "DOWN")
                            last_action_time = current_time
                    prev_scroll_y = wrist_y
                else:
                    prev_scroll_y = None
                    click_count = 0

                if can_launch_app and current_time - last_action_time > GESTURE_COOLDOWN:
                    if thumb_up and not index_up and not middle_up and not ring_up and not pinky_up:
                        subprocess.Popen(['start', 'chrome'], shell=True)
                        gesture_text = "CHROME OPENED"
                        last_app_launch_time = current_time
                        last_action_time = current_time

                    elif thumb_up and index_up and not middle_up and not ring_up and not pinky_up:
                        subprocess.Popen('explorer')
                        gesture_text = "FILE MANAGER OPENED"
                        last_app_launch_time = current_time
                        last_action_time = current_time

                    elif index_up and middle_up and not ring_up and not pinky_up:
                        subprocess.Popen(['start', 'notepad'], shell=True)
                        gesture_text = "NOTEPAD OPENED"
                        last_app_launch_time = current_time
                        last_action_time = current_time

                    elif index_up and pinky_up and not middle_up and not ring_up:
                        subprocess.Popen(['start', 'chrome', 'https://www.youtube.com'], shell=True)
                        gesture_text = "YOUTUBE OPENED"
                        last_app_launch_time = current_time
                        last_action_time = current_time

        if gesture_text:
            cv2.putText(image, gesture_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        cv2.imshow('Gesture Mouse', image)
        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

run_gesture_mouse()