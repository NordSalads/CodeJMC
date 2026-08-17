#!/usr/bin/env python3
"""
Rhythm Game inspired by Project Sekai
Uses librosa for beat detection and pygame for rendering
"""

import os
import sys
import math
import random
import librosa
import numpy as np
import pygame
from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum

# Initialize pygame
pygame.init()
try:
    pygame.mixer.init()
    AUDIO_AVAILABLE = True
except:
    AUDIO_AVAILABLE = False
    print("Audio not available, running in silent mode")

# Screen constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 50, 50)
BLUE = (50, 100, 255)
GREEN = (50, 255, 100)
YELLOW = (255, 255, 50)
PINK = (255, 100, 150)
PURPLE = (150, 50, 255)
CYAN = (50, 255, 255)
GRAY = (100, 100, 100)
DARK_GRAY = (30, 30, 30)

# Game constants
NOTE_SPEED = 500  # pixels per second
HIT_LINE_Y = 500
NOTE_RADIUS = 25
HIT_WINDOW_PERFECT = 0.05  # seconds
HIT_WINDOW_GOOD = 0.10
HIT_WINDOW_MISS = 0.15


class NoteType(Enum):
    TAP = 1
    HOLD = 2
    SLIDE = 3


@dataclass
class Note:
    time: float  # Time in seconds when note should be hit
    lane: int  # 0-3 for 4 lanes
    note_type: NoteType = NoteType.TAP
    duration: float = 0.0  # For hold notes
    hit: bool = False
    missed: bool = False
    
    def get_y(self, current_time: float) -> float:
        """Calculate Y position based on current time"""
        time_until_hit = self.time - current_time
        y = HIT_LINE_Y - (time_until_hit * NOTE_SPEED)
        return y


@dataclass
class Score:
    combo: int = 0
    max_combo: int = 0
    perfect: int = 0
    good: int = 0
    miss: int = 0
    total_score: int = 0
    
    def add_hit(self, accuracy: str):
        self.combo += 1
        self.max_combo = max(self.max_combo, self.combo)
        
        if accuracy == "PERFECT":
            self.perfect += 1
            self.total_score += 1000 + (self.combo * 10)
        elif accuracy == "GOOD":
            self.good += 1
            self.total_score += 500 + (self.combo * 5)
    
    def reset_combo(self):
        self.combo = 0


class RhythmGame:
    def __init__(self, audio_file: Optional[str] = None):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Project Sekai Style Rhythm Game")
        self.clock = pygame.time.Clock()
        
        self.audio_file = audio_file
        self.audio = None
        self.notes: List[Note] = []
        self.current_time = 0.0
        self.audio_start_time = 0.0
        self.is_playing = False
        self.score = Score()
        
        # Lanes configuration (4 lanes like Project Sekai)
        self.num_lanes = 4
        self.lane_width = SCREEN_WIDTH // self.num_lanes
        
        # Load fonts
        self.font_large = pygame.font.Font(None, 72)
        self.font_medium = pygame.font.Font(None, 48)
        self.font_small = pygame.font.Font(None, 32)
        
        # Background image (procedurally generated)
        self.background = self.create_background()
        
        # Character images (placeholder rectangles with colors)
        self.characters = self.create_characters()
        
        # Hit effects
        self.hit_effects = []
        
        # Key states
        self.keys_pressed = [False] * self.num_lanes
        self.key_mapping = [pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k]
        
        # Menu state
        self.state = "menu"  # menu, playing, results
        
        # Combo display animation
        self.combo_scale = 1.0
        self.last_hit_time = 0
        
    def create_background(self) -> pygame.Surface:
        """Create a gradient background"""
        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        
        # Create gradient from dark purple to pink
        for y in range(SCREEN_HEIGHT):
            ratio = y / SCREEN_HEIGHT
            r = int(30 + (255 - 30) * ratio * 0.5)
            g = int(20 + (100 - 20) * ratio * 0.3)
            b = int(60 + (150 - 60) * ratio * 0.4)
            pygame.draw.line(surface, (r, g, b), (0, y), (SCREEN_WIDTH, y))
        
        # Add some decorative lines
        for i in range(20):
            x = random.randint(0, SCREEN_WIDTH)
            y = random.randint(0, SCREEN_HEIGHT)
            length = random.randint(50, 200)
            angle = random.uniform(0, math.pi * 2)
            end_x = x + math.cos(angle) * length
            end_y = y + math.sin(angle) * length
            alpha = random.randint(30, 80)
            color = (*random.choice([PINK, PURPLE, CYAN]), alpha)
            
        return surface
    
    def create_characters(self) -> List[pygame.Surface]:
        """Create placeholder character surfaces"""
        characters = []
        colors = [PINK, BLUE, GREEN, YELLOW]
        
        for i, color in enumerate(colors):
            surface = pygame.Surface((100, 150), pygame.SRCALPHA)
            # Draw a simple character shape
            pygame.draw.ellipse(surface, (*color, 150), (10, 10, 80, 130))
            pygame.draw.circle(surface, (*WHITE, 200), (50, 50), 30)
            characters.append(surface)
        
        return characters
    
    def load_audio(self, audio_file: str):
        """Load audio file and detect beats using librosa"""
        try:
            print(f"Loading audio: {audio_file}")
            y, sr = librosa.load(audio_file, sr=None)
            self.audio = y
            
            # Detect beats
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beats, sr=sr)
            
            print(f"Detected tempo: {tempo:.2f} BPM")
            print(f"Detected {len(beat_times)} beats")
            
            # Generate notes from beats
            self.generate_notes(beat_times)
            
            return True
        except Exception as e:
            print(f"Error loading audio: {e}")
            return False
    
    def generate_notes(self, beat_times: np.ndarray):
        """Generate notes from detected beats"""
        self.notes = []
        
        for i, time in enumerate(beat_times):
            # Skip first few beats (intro)
            if time < 2.0:
                continue
            
            # Randomly assign lanes with patterns
            pattern = i % 8
            
            if pattern < 4:
                # Single notes
                lane = pattern % self.num_lanes
                self.notes.append(Note(time=time, lane=lane, note_type=NoteType.TAP))
            elif pattern == 4:
                # Double note
                self.notes.append(Note(time=time, lane=0, note_type=NoteType.TAP))
                self.notes.append(Note(time=time, lane=3, note_type=NoteType.TAP))
            elif pattern == 5:
                # Hold note
                lane = random.randint(0, self.num_lanes - 1)
                self.notes.append(Note(
                    time=time, 
                    lane=lane, 
                    note_type=NoteType.HOLD,
                    duration=0.5
                ))
            elif pattern == 6:
                # Slide pattern
                self.notes.append(Note(time=time, lane=1, note_type=NoteType.SLIDE))
                self.notes.append(Note(time=time + 0.1, lane=2, note_type=NoteType.SLIDE))
            else:
                # Random single note
                lane = random.randint(0, self.num_lanes - 1)
                self.notes.append(Note(time=time, lane=lane, note_type=NoteType.TAP))
        
        # Sort notes by time
        self.notes.sort(key=lambda n: n.time)
        print(f"Generated {len(self.notes)} notes")
    
    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            if event.type == pygame.KEYDOWN:
                if self.state == "menu":
                    if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        self.start_game()
                    elif event.key == pygame.K_ESCAPE:
                        return False
                
                elif self.state == "playing":
                    # Check key presses for lanes
                    for i, key in enumerate(self.key_mapping):
                        if event.key == key and not self.keys_pressed[i]:
                            self.keys_pressed[i] = True
                            self.check_hit(i)
                
                elif self.state == "results":
                    if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        self.state = "menu"
                        self.reset_game()
                    elif event.key == pygame.K_ESCAPE:
                        return False
            
            if event.type == pygame.KEYUP:
                for i, key in enumerate(self.key_mapping):
                    if event.key == key:
                        self.keys_pressed[i] = False
        
        return True
    
    def check_hit(self, lane: int):
        """Check if a note was hit in the given lane"""
        current_time = self.get_current_time()
        
        # Find hittable notes in this lane
        for note in self.notes:
            if note.lane == lane and not note.hit and not note.missed:
                time_diff = abs(note.time - current_time)
                
                if time_diff < HIT_WINDOW_MISS:
                    note.hit = True
                    
                    if time_diff < HIT_WINDOW_PERFECT:
                        self.score.add_hit("PERFECT")
                        self.add_hit_effect(lane, "PERFECT")
                    elif time_diff < HIT_WINDOW_GOOD:
                        self.score.add_hit("GOOD")
                        self.add_hit_effect(lane, "GOOD")
                    
                    self.combo_scale = 1.5
                    self.last_hit_time = current_time
                    break
    
    def add_hit_effect(self, lane: int, accuracy: str):
        """Add visual hit effect"""
        colors = {
            "PERFECT": YELLOW,
            "GOOD": GREEN,
            "MISS": RED
        }
        self.hit_effects.append({
            'lane': lane,
            'accuracy': accuracy,
            'color': colors.get(accuracy, WHITE),
            'time': pygame.time.get_ticks(),
            'alpha': 255
        })
    
    def get_current_time(self) -> float:
        """Get current audio playback time"""
        if self.is_playing and pygame.mixer.music.get_busy():
            return self.current_time
        return self.current_time
    
    def update(self):
        """Update game state"""
        if self.state == "playing":
            # Update current time
            if pygame.mixer.music.get_busy():
                # Get actual playback position
                pass  # We'll use delta time instead for simplicity
            
            # Check for missed notes
            current_time = self.get_current_time()
            for note in self.notes:
                if not note.hit and not note.missed:
                    if current_time > note.time + HIT_WINDOW_MISS:
                        note.missed = True
                        self.score.reset_combo()
                        self.add_hit_effect(note.lane, "MISS")
            
            # Update combo animation
            if current_time - self.last_hit_time > 0.3:
                self.combo_scale = max(1.0, self.combo_scale - 0.05)
            
            # Check if song is finished
            if len([n for n in self.notes if not n.hit and not n.missed]) == 0:
                if all(n.hit or n.missed for n in self.notes):
                    self.end_game()
    
    def draw_menu(self):
        """Draw main menu"""
        self.screen.blit(self.background, (0, 0))
        
        # Title
        title = self.font_large.render("RHYTHM GAME", True, WHITE)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 150))
        self.screen.blit(title, title_rect)
        
        subtitle = self.font_medium.render("Project Sekai Style", True, PINK)
        subtitle_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, 200))
        self.screen.blit(subtitle, subtitle_rect)
        
        # Instructions
        instructions = [
            "Press ENTER or SPACE to start",
            "Controls: D F J K",
            "Hit notes when they reach the line!"
        ]
        
        for i, text in enumerate(instructions):
            surf = self.font_small.render(text, True, WHITE)
            rect = surf.get_rect(center=(SCREEN_WIDTH // 2, 300 + i * 40))
            self.screen.blit(surf, rect)
        
        # Draw sample lanes
        for i in range(self.num_lanes):
            x = i * self.lane_width
            pygame.draw.line(self.screen, GRAY, (x, HIT_LINE_Y), (x, SCREEN_HEIGHT), 2)
        
        pygame.draw.line(self.screen, WHITE, (0, HIT_LINE_Y), (SCREEN_WIDTH, HIT_LINE_Y), 3)
        
        # Show characters
        for i, char in enumerate(self.characters):
            x = i * self.lane_width + (self.lane_width - 100) // 2
            self.screen.blit(char, (x, HIT_LINE_Y + 20))
    
    def draw_game(self):
        """Draw game screen"""
        self.screen.blit(self.background, (0, 0))
        
        current_time = self.get_current_time()
        
        # Draw lanes
        for i in range(self.num_lanes):
            x = i * self.lane_width
            
            # Lane background
            if self.keys_pressed[i]:
                pygame.draw.rect(self.screen, (50, 50, 80), (x, 0, self.lane_width, SCREEN_HEIGHT))
            
            # Lane divider
            pygame.draw.line(self.screen, GRAY, (x, 0), (x, SCREEN_HEIGHT), 2)
        
        # Draw hit line
        pygame.draw.line(self.screen, WHITE, (0, HIT_LINE_Y), (SCREEN_WIDTH, HIT_LINE_Y), 3)
        
        # Draw notes
        for note in self.notes:
            if note.hit or note.missed:
                continue
            
            y = note.get_y(current_time)
            
            # Only draw visible notes
            if -50 < y < SCREEN_HEIGHT + 50:
                x = note.lane * self.lane_width + self.lane_width // 2
                
                # Note color based on type
                if note.note_type == NoteType.TAP:
                    color = BLUE
                elif note.note_type == NoteType.HOLD:
                    color = PURPLE
                else:
                    color = CYAN
                
                # Draw note
                pygame.draw.circle(self.screen, color, (int(x), int(y)), NOTE_RADIUS)
                pygame.draw.circle(self.screen, WHITE, (int(x), int(y)), NOTE_RADIUS, 2)
                
                # Inner circle for tap notes
                if note.note_type == NoteType.TAP:
                    pygame.draw.circle(self.screen, WHITE, (int(x), int(y)), NOTE_RADIUS // 2)
        
        # Draw hit effects
        current_tick = pygame.time.get_ticks()
        for effect in self.hit_effects[:]:
            elapsed = current_tick - effect['time']
            if elapsed > 500:
                self.hit_effects.remove(effect)
                continue
            
            x = effect['lane'] * self.lane_width + self.lane_width // 2
            alpha = max(0, 255 - (elapsed / 500) * 255)
            
            # Draw explosion effect
            radius = NOTE_RADIUS + (elapsed / 500) * 30
            color_with_alpha = (*effect['color'][:3], int(alpha))
            
            # Draw text
            text = self.font_small.render(effect['accuracy'], True, effect['color'])
            text_rect = text.get_rect(center=(x, HIT_LINE_Y - 50 - elapsed / 10))
            self.screen.blit(text, text_rect)
        
        # Draw score and combo
        score_text = self.font_medium.render(f"Score: {self.score.total_score}", True, WHITE)
        self.screen.blit(score_text, (20, 20))
        
        # Combo display with animation
        if self.score.combo > 0:
            combo_size = int(72 * self.combo_scale)
            combo_font = pygame.font.Font(None, combo_size)
            combo_text = combo_font.render(f"{self.score.combo} COMBO", True, YELLOW)
            combo_rect = combo_text.get_rect(center=(SCREEN_WIDTH // 2, 150))
            
            # Glow effect
            glow_surf = pygame.Surface((combo_rect.width + 20, combo_rect.height + 20), pygame.SRCALPHA)
            pygame.draw.ellipse(glow_surf, (*YELLOW, 50), glow_surf.get_rect())
            self.screen.blit(glow_surf, (combo_rect.x - 10, combo_rect.y - 10))
            
            self.screen.blit(combo_text, combo_rect)
        
        # Draw lane indicators at bottom
        for i in range(self.num_lanes):
            x = i * self.lane_width + self.lane_width // 2
            key_name = ["D", "F", "J", "K"][i]
            
            if self.keys_pressed[i]:
                pygame.draw.circle(self.screen, WHITE, (x, HIT_LINE_Y), NOTE_RADIUS + 5, 3)
            
            key_text = self.font_small.render(key_name, True, WHITE)
            key_rect = key_text.get_rect(center=(x, HIT_LINE_Y + 60))
            self.screen.blit(key_text, key_rect)
    
    def draw_results(self):
        """Draw results screen"""
        self.screen.fill(DARK_GRAY)
        
        # Title
        title = self.font_large.render("RESULTS", True, WHITE)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 100))
        self.screen.blit(title, title_rect)
        
        # Stats
        stats = [
            f"Score: {self.score.total_score}",
            f"Max Combo: {self.score.max_combo}",
            f"Perfect: {self.score.perfect}",
            f"Good: {self.score.good}",
            f"Miss: {self.score.miss}"
        ]
        
        total_notes = self.score.perfect + self.score.good + self.score.miss
        if total_notes > 0:
            accuracy = (self.score.perfect * 100 + self.score.good * 50) / (total_notes * 100)
            stats.append(f"Accuracy: {accuracy:.1f}%")
        
        for i, text in enumerate(stats):
            surf = self.font_medium.render(text, True, WHITE)
            rect = surf.get_rect(center=(SCREEN_WIDTH // 2, 200 + i * 50))
            self.screen.blit(surf, rect)
        
        # Rank
        total_notes = self.score.perfect + self.score.good + self.score.miss
        if total_notes > 0:
            accuracy = (self.score.perfect * 100 + self.score.good * 50) / (total_notes * 100)
            
            if accuracy >= 95:
                rank = "S"
                rank_color = YELLOW
            elif accuracy >= 90:
                rank = "A"
                rank_color = GREEN
            elif accuracy >= 80:
                rank = "B"
                rank_color = BLUE
            elif accuracy >= 70:
                rank = "C"
                rank_color = CYAN
            else:
                rank = "D"
                rank_color = RED
            
            rank_surf = self.font_large.render(f"Rank: {rank}", True, rank_color)
            rank_rect = rank_surf.get_rect(center=(SCREEN_WIDTH // 2, 450))
            self.screen.blit(rank_surf, rank_rect)
        
        # Restart instruction
        restart = self.font_small.render("Press ENTER to return to menu", True, WHITE)
        restart_rect = restart.get_rect(center=(SCREEN_WIDTH // 2, 550))
        self.screen.blit(restart, restart_rect)
    
    def draw(self):
        """Draw current frame"""
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "playing":
            self.draw_game()
        elif self.state == "results":
            self.draw_results()
        
        pygame.display.flip()
    
    def start_game(self):
        """Start the game"""
        self.state = "playing"
        self.score = Score()
        self.current_time = 0.0
        self.hit_effects = []
        
        # Reset notes
        for note in self.notes:
            note.hit = False
            note.missed = False
        
        # Play audio if available
        if self.audio_file and os.path.exists(self.audio_file) and AUDIO_AVAILABLE:
            try:
                pygame.mixer.music.load(self.audio_file)
                pygame.mixer.music.play()
                self.is_playing = True
            except Exception as e:
                print(f"Error playing audio: {e}")
                self.is_playing = False
        else:
            self.is_playing = False
            if not AUDIO_AVAILABLE:
                print("Audio device not available, running in demo mode")
            elif not self.audio_file:
                print("No audio file, running in demo mode")
    
    def end_game(self):
        """End the game and show results"""
        self.state = "results"
        self.is_playing = False
        pygame.mixer.music.stop()
    
    def reset_game(self):
        """Reset game state"""
        self.score = Score()
        self.current_time = 0.0
        self.hit_effects = []
        
        for note in self.notes:
            note.hit = False
            note.missed = False
    
    def run(self):
        """Main game loop"""
        running = True
        
        while running:
            dt = self.clock.tick(FPS) / 1000.0  # Delta time in seconds
            
            running = self.handle_events()
            
            if self.state == "playing":
                self.current_time += dt
                self.update()
            
            self.draw()
        
        pygame.quit()


def main():
    """Main entry point"""
    print("=" * 50)
    print("Project Sekai Style Rhythm Game")
    print("=" * 50)
    print()
    print("Controls:")
    print("  D, F, J, K - Hit notes in corresponding lanes")
    print("  ENTER/SPACE - Start game / Continue")
    print("  ESC - Quit")
    print()
    
    # Check for audio file
    audio_file = None
    
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        if not os.path.exists(audio_file):
            print(f"Audio file not found: {audio_file}")
            print("Running without audio...")
            audio_file = None
    else:
        print("No audio file specified.")
        print("Usage: python rhythm_game.py <audio_file.mp3>")
        print("Running in demo mode...")
        print()
    
    # Create and run game
    game = RhythmGame(audio_file)
    
    # If audio file provided, try to load it
    if audio_file:
        if not game.load_audio(audio_file):
            print("Failed to load audio, generating demo notes...")
            # Generate demo notes
            demo_beats = np.array([i * 0.5 for i in range(2, 100)])
            game.generate_notes(demo_beats)
    else:
        # Generate demo notes
        print("Generating demo pattern...")
        demo_beats = np.array([i * 0.5 + 2.0 for i in range(100)])
        game.generate_notes(demo_beats)
    
    print()
    print("Starting game...")
    game.run()


if __name__ == "__main__":
    main()
