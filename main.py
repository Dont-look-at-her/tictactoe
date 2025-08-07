import discord
from discord.ext import commands
import random
import os
import json
from datetime import datetime

# Fun quotes for wins and ties
win_quotes = [
    "You just toe-tally dominated.",
    "Game over. Better luck next tic.",
    "Winner, winner, grid square dinner!",
    "You laid that ❌ smackdown.",
    "They never stood a chance…",
    "That win was cleaner than a fresh pedicure.",
    "Toe-tally illegal levels of strategy right there.",
    "Victory tastes like chalk dust and tears.",
    "The board has spoken—and it says you SLAY.",
    "Another soul crushed in 3x3 silence.",
    "You crossed them out like a mistake in pen.",
    "Congratulations! You're now a licensed board bully.",
    "Checkmate—wait wrong game—but still, SLAY.",
    "Victory called. You answered with a middle square.",
    "Your opponent? Toe-st.",
    "That win was more satisfying than a bubble wrap pop.",
    "The prophecy was true: you're unstoppable.",
    "They brought ✋, you brought 🧠.",
    "The squares align... for YOU, my champion.",
    "Who taught you that? The Toe-chiha clan??",
    "Toe-to-toe and still crushed them!"
]

tie_quotes = [
    "Nobody wins, everybody's salty.",
    "It's a draw! Like watching paint dry, but with more X's and O's.",
    "Stalemate city, population: you two.",
    "Both of you played... adequately.",
    "The board is full of regret and missed opportunities.",
    "A tie! How beautifully mediocre.",
    "You both lost... to the concept of winning.",
    "Draw! The universe remains unimpressed.",
    "Nobody won, but at least nobody lost... wait.",
    "It's a tie! Time to question your life choices.",
    "The squares are full, but your hearts are empty.",
    "Draw game! You're equally matched in disappointment.",
    "Congratulations on achieving mutual failure!",
    "A draw! Even the board is confused.",
    "Tie game! You both deserve participation trophies."
]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

active_games = {}  # {channel_id: TicTacToe instance}

# Stats storage
STATS_FILE = "player_stats.json"

def load_stats():
    """Load player statistics from JSON file"""
    try:
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_stats(stats):
    """Save player statistics to JSON file"""
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2)

def update_player_stats(player_id, won=False, draw=False):
    """Update statistics for a player"""
    stats = load_stats()
    player_id = str(player_id)

    if player_id not in stats:
        stats[player_id] = {
            'wins': 0,
            'losses': 0,
            'draws': 0,
            'games_played': 0,
            'last_played': None
        }

    stats[player_id]['games_played'] += 1
    stats[player_id]['last_played'] = datetime.now().isoformat()

    if won:
        stats[player_id]['wins'] += 1
    elif draw:
        stats[player_id]['draws'] += 1
    else:
        stats[player_id]['losses'] += 1

    save_stats(stats)

def get_win_rate(stats):
    """Calculate win rate percentage"""
    if stats['games_played'] == 0:
        return 0.0
    return (stats['wins'] / stats['games_played']) * 100

class TicTacToeButton(discord.ui.Button):
    def __init__(self, row, col, game):
        super().__init__(label="⬛", style=discord.ButtonStyle.secondary, row=row)
        self.row = row
        self.col = col
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        if self.game.game_over:
            await interaction.response.send_message("Game is already over!", ephemeral=True)
            return

        # Check if the user is one of the players in this game
        if interaction.user.id not in [self.game.player1, self.game.player2]:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return

        # Check if user has used !tttend (makes board unclickable for them)
        if interaction.user.id in self.game.players_used_tttend:
            await interaction.response.send_message("You ended this game and cannot play on it anymore!", ephemeral=True)
            return

        if interaction.user.id != self.game.current_player and not self.game.is_bot_game:
            await interaction.response.send_message("Not your turn!", ephemeral=True)
            return

        if self.game.is_bot_game and interaction.user.id == bot.user.id:
            await interaction.response.send_message("It's the bot's turn!", ephemeral=True)
            return

        if self.label != "⬛":
            await interaction.response.send_message("That space is taken!", ephemeral=True)
            return

        mark = "❌" if self.game.current_player == self.game.player1 else "⭕"
        self.label = mark
        self.disabled = True
        self.game.board[self.row][self.col] = mark

        if self.game.check_winner():
            self.view.disable_all_items()
            winner_id = self.game.current_player
            loser_id = self.game.player2 if winner_id == self.game.player1 else self.game.player1

            # Update stats
            update_player_stats(winner_id, won=True)
            update_player_stats(loser_id, won=False)

            # Get random win quote
            win_quote = random.choice(win_quotes)

            # Add rematch button
            rematch_view = discord.ui.View(timeout=None)
            rematch_view.add_item(RematchButton(self.game.player1, self.game.player2, self.game.is_bot_game))

            await interaction.response.edit_message(
                content=f"{interaction.user.mention} wins! 🎉\n*{win_quote}*", view=rematch_view
            )

            self.game.game_over = True
            if interaction.channel.id in active_games:
                del active_games[interaction.channel.id]
        elif self.game.is_draw():
            self.view.disable_all_items()

            # Update stats for both players (draw)
            update_player_stats(self.game.player1, draw=True)
            update_player_stats(self.game.player2, draw=True)

            # Get random tie quote
            tie_quote = random.choice(tie_quotes)

            # Add rematch button
            rematch_view = discord.ui.View(timeout=None)
            rematch_view.add_item(RematchButton(self.game.player1, self.game.player2, self.game.is_bot_game))

            await interaction.response.edit_message(content=f"It's a draw! 🤝\n*{tie_quote}*", view=rematch_view)
            self.game.game_over = True
            if interaction.channel.id in active_games:
                del active_games[interaction.channel.id]
        else:
            self.game.switch_turn()

            if self.game.current_player == bot.user.id:
                next_player = bot.user
            else:
                next_player = await bot.fetch_user(self.game.current_player)

            await interaction.response.edit_message(
                content=f"{next_player.mention}, it's your turn!", view=self.view
            )

            # If it's the bot's turn, make a move
            if self.game.is_bot_game and self.game.current_player == bot.user.id:
                await self.game.make_bot_move(interaction)

class RematchButton(discord.ui.Button):
    def __init__(self, player1, player2, is_bot_game=False):
        super().__init__(label="Rematch", style=discord.ButtonStyle.primary, emoji="🔄")
        self.player1 = player1
        self.player2 = player2
        self.is_bot_game = is_bot_game

    async def callback(self, interaction: discord.Interaction):
        # For bot games, only the human player can start rematch
        if self.is_bot_game:
            human_player = self.player1 if self.player1 != bot.user.id else self.player2
            if interaction.user.id != human_player:
                await interaction.response.send_message("Only you can start a rematch!", ephemeral=True)
                return
        else:
            if interaction.user.id not in [self.player1, self.player2]:
                await interaction.response.send_message("Only the players can start a rematch!", ephemeral=True)
                return

        # Start a new game
        new_game = TicTacToe(self.player1, self.player2, is_bot_game=self.is_bot_game)
        active_games[interaction.channel.id] = new_game

        if self.is_bot_game:
            if new_game.current_player == bot.user.id:
                current_user = bot.user
            else:
                current_user = await bot.fetch_user(new_game.current_player)
            await interaction.response.edit_message(
                content=f"Rematch started! {current_user.mention}, it's your turn!",
                view=new_game
            )
            # If bot goes first in rematch, make a move
            if new_game.current_player == bot.user.id:
                await new_game.make_bot_move(interaction)
        else:
            current_user = await bot.fetch_user(new_game.current_player)
            await interaction.response.edit_message(
                content=f"Rematch started! {current_user.mention}, it's your turn!",
                view=new_game
            )

class TicTacToe(discord.ui.View):
    def __init__(self, player1, player2, is_bot_game=False):
        super().__init__(timeout=None)
        self.player1 = player1
        self.player2 = player2
        self.current_player = random.choice([player1, player2])
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.game_over = False
        self.is_bot_game = is_bot_game
        self.players_used_tttend = set()

        for i in range(3):
            for j in range(3):
                self.add_item(TicTacToeButton(i, j, self))

    def disable_all_items(self):
        """Disable all buttons in this view"""
        for item in self.children:
            item.disabled = True

    def get_current_mention(self):
        return f"<@{self.current_player}>" if self.current_player != bot.user.id else f"{bot.user.mention} (Bot)"

    def switch_turn(self):
        if self.current_player == self.player1:
            self.current_player = self.player2
        else:
            self.current_player = self.player1

    def check_winner(self):
        # Check rows
        for row in self.board:
            if row[0] == row[1] == row[2] and row[0] != "":
                return True

        # Check columns
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] and self.board[0][col] != "":
                return True

        # Check diagonals
        if self.board[0][0] == self.board[1][1] == self.board[2][2] and self.board[0][0] != "":
            return True
        if self.board[0][2] == self.board[1][1] == self.board[2][0] and self.board[0][2] != "":
            return True

        return False

    def is_draw(self):
        for row in self.board:
            for cell in row:
                if cell == "":
                    return False
        return True

    def find_winning_move(self, symbol):
        """Find a move that would win the game"""
        for i in range(3):
            for j in range(3):
                if self.board[i][j] == "":
                    # Try this move
                    self.board[i][j] = symbol
                    if self.check_winner():
                        self.board[i][j] = ""  # Undo the move
                        return (i, j)
                    self.board[i][j] = ""  # Undo the move
        return None

    def find_blocking_move(self, opponent_symbol):
        """Find a move that would block the opponent from winning"""
        for i in range(3):
            for j in range(3):
                if self.board[i][j] == "":
                    # Try opponent's move
                    self.board[i][j] = opponent_symbol
                    if self.check_winner():
                        self.board[i][j] = ""  # Undo the move
                        return (i, j)
                    self.board[i][j] = ""  # Undo the move
        return None

    def get_center_move(self):
        """Take center if available"""
        if self.board[1][1] == "":
            return (1, 1)
        return None

    def get_corner_move(self):
        """Take a corner if available"""
        corners = [(0, 0), (0, 2), (2, 0), (2, 2)]
        available_corners = [corner for corner in corners if self.board[corner[0]][corner[1]] == ""]
        if available_corners:
            return random.choice(available_corners)
        return None

    def get_random_move(self):
        """Get any available move"""
        available_moves = []
        for i in range(3):
            for j in range(3):
                if self.board[i][j] == "":
                    available_moves.append((i, j))
        if available_moves:
            return random.choice(available_moves)
        return None

    async def make_bot_move(self, interaction: discord.Interaction):
        # Get bot's symbol and human's symbol
        bot_symbol = "❌" if self.current_player == self.player1 else "⭕"
        human_symbol = "⭕" if bot_symbol == "❌" else "❌"

        # Always prioritize winning and blocking (these are critical)
        move = self.find_winning_move(bot_symbol) or self.find_blocking_move(human_symbol)
        
        if not move:
            # Add randomization to make the bot less predictable
            available_strategies = []
            
            # Add center strategy (60% chance to include it)
            if self.get_center_move() and random.random() < 0.6:
                available_strategies.append(self.get_center_move())
            
            # Add corner strategy (always include if corners available)
            corner_move = self.get_corner_move()
            if corner_move:
                available_strategies.append(corner_move)
            
            # Add random moves to the pool (add 2-3 random options)
            for _ in range(random.randint(2, 3)):
                random_move = self.get_random_move()
                if random_move:
                    available_strategies.append(random_move)
            
            # Choose randomly from available strategies
            if available_strategies:
                move = random.choice(available_strategies)
            else:
                move = self.get_random_move()

        if move:
            row, col = move
            button = None
            for item in self.children:
                if isinstance(item, TicTacToeButton) and item.row == row and item.col == col:
                    button = item
                    break

            if button:
                mark = "❌" if self.current_player == self.player1 else "⭕"
                button.label = mark
                button.disabled = True
                self.board[row][col] = mark

                if self.check_winner():
                    self.disable_all_items()
                    winner_id = self.current_player
                    loser_id = self.player2 if winner_id == self.player1 else self.player1

                    # Update stats
                    update_player_stats(winner_id, won=True)
                    update_player_stats(loser_id, won=False)

                    # Get random win quote
                    win_quote = random.choice(win_quotes)

                    # Add rematch button
                    rematch_view = discord.ui.View(timeout=None)
                    rematch_view.add_item(RematchButton(self.player1, self.player2, self.is_bot_game))

                    await interaction.followup.edit_message(
                        interaction.message.id,
                        content=f"{bot.user.mention} wins! 🎉\n*{win_quote}*", view=rematch_view
                    )

                    # Send ephemeral congratulations to winner
                    #await interaction.followup.send(f"🎉 Congratulations! {win_quote}", ephemeral=True) #Bot doesn't need to be congratulated
                    self.game_over = True
                    if interaction.channel.id in active_games:
                        del active_games[interaction.channel.id]
                elif self.is_draw():
                    self.disable_all_items()

                    # Update stats for both players (draw)
                    update_player_stats(self.player1, draw=True)
                    update_player_stats(self.player2, draw=True)

                    # Get random tie quote
                    tie_quote = random.choice(tie_quotes)

                    # Add rematch button
                    rematch_view = discord.ui.View(timeout=None)
                    rematch_view.add_item(RematchButton(self.player1, self.player2, self.is_bot_game))

                    await interaction.followup.edit_message(
                        interaction.message.id,
                        content=f"It's a draw! 🤝\n*{tie_quote}*", view=rematch_view
                    )
                    self.game_over = True
                    if interaction.channel.id in active_games:
                        del active_games[interaction.channel.id]
                else:
                    self.switch_turn()
                    if self.current_player == bot.user.id:
                        next_player = bot.user
                    else:
                        next_player = await bot.fetch_user(self.current_player)
                    await interaction.followup.edit_message(
                        interaction.message.id,
                        content=f"{next_player.mention}, it's your turn!", view=self
                    )
class ChallengeView(discord.ui.View):
    def __init__(self, challenger, opponent, is_bot_game=False):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.is_bot_game = is_bot_game

    def disable_buttons(self):
        """Disable all buttons in this view"""
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id and not self.is_bot_game:
            await interaction.response.send_message("This challenge is not for you!", ephemeral=True)
            return

        if self.is_bot_game and interaction.user.id != self.challenger.id:
            await interaction.response.send_message("This challenge is not for you!", ephemeral=True)
            return

        self.disable_buttons()
        game = TicTacToe(self.challenger.id, self.opponent.id, is_bot_game=self.is_bot_game)
        active_games[interaction.channel.id] = game

        if game.current_player == bot.user.id:
            next_player = bot.user
        else:
            next_player = await bot.fetch_user(game.current_player)

        await interaction.response.edit_message(
            content=f"Game started! {next_player.mention}, it's your turn!", 
            view=game
        )

        #If bot goes first make the first move
        if self.is_bot_game and game.current_player == bot.user.id:
            await game.make_bot_move(interaction)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id and not self.is_bot_game:
            await interaction.response.send_message("This challenge is not for you!", ephemeral=True)
            return

        if self.is_bot_game and interaction.user.id != self.challenger.id:
            await interaction.response.send_message("This challenge is not for you!", ephemeral=True)
            return

        self.disable_buttons()
        if not self.is_bot_game:
            await interaction.response.edit_message(
                content=f"{self.opponent.mention} declined the challenge.", 
                view=self
            )
        else:
            await interaction.response.edit_message(
                content=f"{self.challenger.mention} declined to play against the bot.",
                view = self
            )

    async def on_timeout(self):
        self.disable_buttons()
        # Note: The message won't auto-update on timeout, but buttons will be disabled

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command(name="ttt")
async def tic_tac_toe(ctx, opponent: discord.Member = None):
    if opponent is None:
        await ctx.send("Please mention a user to challenge! Usage: `!ttt @username`")
        return

    if opponent.bot:
        await ctx.send("You can't challenge a bot!")
        return

    if opponent.id == ctx.author.id:
        await ctx.send("You can't challenge yourself!")
        return

    if ctx.channel.id in active_games:
        await ctx.send("There's already a game running in this channel!")
        return

    view = ChallengeView(ctx.author, opponent)
    await ctx.send(
        f"{opponent.mention}, you've been challenged to a game of Tic Tac Toe by {ctx.author.mention}!",
        view=view
    )

@bot.command(name="tttbot")
async def tic_tac_toe_bot(ctx):
    """Challenge the bot to a game of Tic Tac Toe"""
    if ctx.channel.id in active_games:
        await ctx.send("There's already a game running in this channel!")
        return

    view = ChallengeView(ctx.author, bot.user, is_bot_game=True)
    await ctx.send(
        f"{ctx.author.mention}, you've challenged the bot to a game of Tic Tac Toe!",
        view=view
    )

@bot.command(name="tttstats")
async def player_stats(ctx, player: discord.Member = None):
    """Show statistics for a player"""
    if player is None:
        player = ctx.author

    stats = load_stats()
    player_id = str(player.id)

    if player_id not in stats:
        await ctx.send(f"{player.display_name} hasn't played any games yet!")
        return

    player_stats = stats[player_id]
    win_rate = get_win_rate(player_stats)

    embed = discord.Embed(
        title=f"📊 {player.display_name}'s Tic Tac Toe Stats",
        color=discord.Color.blue()
    )

    embed.add_field(name="🎮 Games Played", value=player_stats['games_played'], inline=True)
    embed.add_field(name="🏆 Wins", value=player_stats['wins'], inline=True)
    embed.add_field(name="💔 Losses", value=player_stats['losses'], inline=True)
    embed.add_field(name="🤝 Draws", value=player_stats['draws'], inline=True)
    embed.add_field(name="📈 Win Rate", value=f"{win_rate:.1f}%", inline=True)

    if player_stats['last_played']:
        last_played = datetime.fromisoformat(player_stats['last_played'])
        embed.add_field(name="🕐 Last Played", value=last_played.strftime("%Y-%m-%d %H:%M"), inline=True)

    embed.set_thumbnail(url=player.avatar.url if player.avatar else None)

    await ctx.send(embed=embed)

@bot.command(name="tttleaderboard")
async def leaderboard(ctx):
    """Show the top players leaderboard"""
    stats = load_stats()

    if not stats:
        await ctx.send("No games have been played yet!")
        return

    # Filter players with at least 1 game and sort by wins, then by win rate
    player_list = []
    for player_id, player_stats in stats.items():
        if player_stats['games_played'] > 0:
            try:
                user = await bot.fetch_user(int(player_id))
                win_rate = get_win_rate(player_stats)
                player_list.append({
                    'name': user.display_name,
                    'wins': player_stats['wins'],
                    'games': player_stats['games_played'],
                    'win_rate': win_rate
                })
            except:
                # Skip if user not found
                continue

    # Sort by wins (descending), then by win rate (descending)
    player_list.sort(key=lambda x: (x['wins'], x['win_rate']), reverse=True)

    embed = discord.Embed(
        title="🏆 Tic Tac Toe Leaderboard",
        description="Top players ranked by wins and win rate",
        color=discord.Color.gold()
    )

    # Show top 10 players
    for i, player in enumerate(player_list[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."

        embed.add_field(
            name=f"{medal} {player['name']}",
            value=f"**{player['wins']}** wins • **{player['win_rate']:.1f}%** win rate • **{player['games']}** games",
            inline=False
        )

    if not player_list:
        embed.description = "No players found!"

    await ctx.send(embed=embed)

@bot.command(name="tttend")
async def end_game(ctx):
    """Force-end the current game in this channel"""
    if ctx.channel.id not in active_games:
        await ctx.send("There's no active game in this channel to end.")
        return

    game = active_games[ctx.channel.id]

    # Check if the user is one of the players in the game
    if ctx.author.id not in [game.player1, game.player2]:
        await ctx.send("Only players in the current game can end it!")
        return

    if ctx.author.id in game.players_used_tttend:
        await ctx.send("You have already ended this game!")
        return

    # Add the player to the set of players who have used !tttend
    game.players_used_tttend.add(ctx.author.id)

    # Disable the game board and mark it as over
    game.disable_all_items()
    game.game_over = True
    
    # Remove the game from active games
    del active_games[ctx.channel.id]
    
    await ctx.send(f"🛑 Game ended by {ctx.author.mention}. You can start a new game now!")

@bot.command(name="ttthelp")
async def tic_tac_toe_help(ctx):
    """Show help information for the Tic Tac Toe bot"""
    embed = discord.Embed(
        title="🎮 Tic Tac Toe Bot Help",
        description="Learn how to play and use all the bot features!",
        color=discord.Color.green()
    )

    embed.add_field(
        name="🎯 How to Play",
        value="Challenge someone to a game and take turns clicking squares to get 3 in a row!",
        inline=False
    )

    embed.add_field(
        name="📋 Commands",
        value="`!ttt @username` - Challenge a user to play\n"
              "`!tttbot` - Challenge the bot to play\n"
              "`!tttstats [@user]` - View your stats or another player's\n"
              "`!tttleaderboard` - See the top players\n"
              "`!tttend` - Force-end the current game\n"
              "`!ttthelp` - Show this help message",
        inline=False
    )

    embed.add_field(
        name="🎮 Game Rules",
        value="• One game per channel at a time\n"
              "• Random player goes first (❌ or ⭕)\n"
              "• Click Accept/Decline within 60 seconds\n"
              "• Click empty squares to make your move\n"
              "• First to get 3 in a row wins!",
        inline=False
    )

    embed.add_field(
        name="📊 Statistics",
        value="The bot tracks your wins, losses, draws, and win rate automatically!\n"
              "Check your progress with `!tttstats` or compete on the `!tttleaderboard`",
        inline=False
    )

    embed.add_field(
        name="🚫 Restrictions",
        value="• Can't challenge bots (except with !tttbot)\n"
              "• Can't challenge yourself\n"
              "• Can't start multiple games in same channel",
        inline=False
    )

    embed.set_footer(text="Have fun playing Tic Tac Toe! 🎉")

    await ctx.send(embed=embed)

# Use environment variable for bot token
bot.run(os.getenv('DISCORD_TOKEN'))