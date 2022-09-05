'''gym wrapper for McOsu, a remake of osu! but without anticheats preventing pyautogui/win32api from moving the cursor around'''
import cv2
import gym
import time
import random
import pyautogui
import win32api
import pydirectinput
import numpy as np
from mss import mss
from collections import deque

from utils.scoring import *
from utils.click import *


class McOsu(gym.Env):
    def __init__(self, bounding_box, hardcode_list, done_screen):
        super().__init__()
        
        self.action_space = gym.spaces.Discrete(100)
        
        # screen capture resolution (h, w)
        self.resolution = (600, 800, 3)
        self.observation_space = gym.spaces.Box(
            low=0,
            high=255,
            shape=self.resolution
        )
        
        # parameters for screen capture
        self.bounding_box = bounding_box
        self.hardcode_list = hardcode_list
        self.done_screen = done_screen
        
        self.sc = mss()
        self.last_score = 0
        self.done = False
        self.score_buffer = deque(maxlen=100)
        
    def step(self, action): # action 
        
        self._apply_action(action)
        
        sct_img = self.sc.grab(self.bounding_box)
        frame = np.array(sct_img)[:, :, 0:3]
        
        # recognizes that the retry screen has appeared, error catch for done parameters 1 and 2
        if (sum(sum(sum(frame == self.done_screen))) >= 1300000):
            self.done = True
        
        # in osu, if score != 0 and does not change for some time (no hits), health decays rapidly
        # can use this functionality as a 'done' parameter
        if (len(self.score_buffer) == self.score_buffer.maxlen) and (len(set(self.score_buffer)) == 1 and self.score_buffer[0] != 0):
            self.done = True
        
        score = frame[13:40, 650:800, :]
        score = int(get_score(score, self.hardcode_list))
        
        # error catch for when the score is noticeably miscalcualted
        if (len(str(score)) - len(str(self.last_score)) > 2 or self.last_score > score): 
            score = self.last_score
        
        self.score_buffer.append(score)
        reward = score - self.last_score
        
        self.last_score = score
        
        return frame, score, self.done
    
    def reset(self):
        self.score_buffer.clear()
        self.last_score = 0
        self.done = False
        
        time.sleep(10) # wait for death animation to finish and reset screen to pop up
        
        
        pyautogui.moveTo(990, 535)
        time.sleep(1)
        leftClick() # win32api, pyautogui doesnt work for click
        
        time.sleep(3) # wait for beatmap to load in 
        
        # current frame
        self.current_frame = np.array(self.sc.grab(self.bounding_box))[:, :, 0:3]
        return self.current_frame
    
    def _apply_action(self, action):
        # conquer relax mode first:
            # actions are either moveTo(x, y), or do nothing
        x, y = action
        # win32api.SetCursorPos(action)
        pydirectinput.moveTo(x, y)
        time.sleep(0.1)
        leftClick()