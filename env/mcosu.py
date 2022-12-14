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
        
        # parameters for screen capture
        self.bounding_box = bounding_box
        self.hardcode_list = hardcode_list
        self.done_screen = done_screen
        
        # apply a margin to the screen since no circles appear on the very left/right/top/bottom of the map
        margin = 30
        self.xl_bound = self.bounding_box['left'] + margin
        self.xr_bound = self.bounding_box['left'] + self.bounding_box['width'] - margin
        self.yt_bound = self.bounding_box['top'] + margin
        self.yb_bound = self.bounding_box['top'] + self.bounding_box['height'] - margin
        
        self.action_space = gym.spaces.Box(
            low=np.array([self.xl_bound, self.yt_bound]),
            high=np.array([self.xr_bound, self.yb_bound]),
            shape=(2, ),
            dtype=np.float32
        )
        
        # screen capture resolution (h, w)
        self.resolution = (600, 800, 3)
        self.observation_space = gym.spaces.Box(
            low=0,
            high=255,
            shape=self.resolution,
            dtype=np.uint8
        )
        
        self.sc = mss()
        self.last_score = 0
        self.done = False
        self.score_buffer = deque(maxlen=100)
        
        self.q_table = np.load('env/q_table.npy')
        
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
        
        # stable baselines3 asserts 4 return values (where info must be a python dictionary)
        frame = self.process_frame(frame)
        return frame, reward, self.done, {}
    
    def reset(self):
        self.score_buffer.clear()
        self.last_score = 0
        self.done = False
        
        time.sleep(5) # wait for death animation to finish and reset screen to pop up
        
        
        pydirectinput.moveTo(990, 535)
        time.sleep(1)
        leftClick() # win32api, pyautogui doesnt work for click
        
        time.sleep(1) # wait for beatmap to load in 
        
        # current frame
        self.current_frame = np.array(self.sc.grab(self.bounding_box))[:, :, 0:3]
        self.current_frame = self.process_frame(self.current_frame)
        return self.current_frame
    
    def _apply_action(self, action):
        # conquer relax mode first
        # actions are either moveTo(x, y), or do nothing
        
        if action == 30000: # do nothing
            return 
        
        x, y = self.q_table[action]
        x, y = int(x), int(y)
        
        pydirectinput.moveTo(x, y)
        # leftClick()
    
    def _get_random_action(self, margin=30):
        if np.random.rand() > 0.5:
            action = np.random.randint(0, 30000)
            loc = self.q_table[action]
            pydirectinput.moveTo(loc[0], loc[1])
        else:
            action = None
            
        return action
        
    def process_frame(self, ob):
        ob = cv2.cvtColor(ob, cv2.COLOR_BGR2GRAY)
        ob = cv2.resize(ob, dsize=(84, 84))
        return ob
        
        