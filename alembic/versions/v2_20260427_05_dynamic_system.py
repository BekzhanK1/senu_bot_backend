"""Dynamic content and menu system

Revision ID: v2_core_005
Revises: v2_core_004
Create Date: 2026-04-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'v2_core_005'
down_revision = 'v2_core_004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add permissions column to roles table
    op.add_column('roles', sa.Column('permissions', sa.Text(), nullable=True))
    
    # Create dynamic_content table
    op.create_table(
        'dynamic_content',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(length=128), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_type', sa.String(length=32), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    op.create_index(op.f('ix_dynamic_content_key'), 'dynamic_content', ['key'], unique=False)
    
    # Create menu_buttons table
    op.create_table(
        'menu_buttons',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('text', sa.String(length=128), nullable=False),
        sa.Column('action_type', sa.String(length=32), nullable=False),
        sa.Column('action_value', sa.String(length=256), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('icon', sa.String(length=16), nullable=True),
        sa.Column('required_role', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Insert default menu buttons
    op.execute("""
        INSERT INTO menu_buttons (text, action_type, action_value, position, is_active, icon, created_at)
        VALUES 
        ('📅 Запись на встречу', 'command', 'meeting_start', 1, true, '📅', CURRENT_TIMESTAMP),
        ('❓ Задать вопрос', 'command', 'question_start', 2, true, '❓', CURRENT_TIMESTAMP),
        ('🎭 Игра «108»', 'command', 'game_108', 3, true, '🎭', CURRENT_TIMESTAMP),
        ('💡 Совет дня', 'command', 'tip', 4, true, '💡', CURRENT_TIMESTAMP),
        ('💎 Ментор Айнур', 'command', 'about_mentor', 5, true, '💎', CURRENT_TIMESTAMP),
        ('🚑 Помощь (PCS)', 'command', 'pcs_help', 6, true, '🚑', CURRENT_TIMESTAMP),
        ('👤 Мой профиль', 'command', 'profile', 7, true, '👤', CURRENT_TIMESTAMP),
        ('🆘 Мне тяжело сейчас', 'command', 'crisis', 8, true, '🆘', CURRENT_TIMESTAMP)
    """)
    
    # Insert default dynamic content
    op.execute("""
        INSERT INTO dynamic_content (key, content, content_type, category, description, created_at, updated_at)
        VALUES 
        ('crisis_grounding', '🫂 <b>Спасибо, что написал(а).</b> То, что ты чувствуешь — важно.\n\nСделай 3 медленных вдоха: вдох на 4 счёта — пауза — выдох на 6.\nЕсли хочешь, положи руку на грудь и назови вслух один предмет рядом с собой.\n\nКогда будешь готов(а) продолжить, нажми кнопку ниже.', 'html', 'crisis', 'Grounding message for crisis intervention', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('crisis_pcs_block', '\n\n<b>🆘 Если тебе нужна срочная поддержка прямо сейчас:</b>\n• Бот PCS: @pcs_nu_bot\n• Телефон доверия: <b>111</b>\nТы не обязан(а) справляться один(а).', 'html', 'crisis', 'PCS contact information block', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('notify_status_change', '\n\n📬 <i>Когда статус заявки изменится, я пришлю уведомление сюда.</i>', 'html', 'notification', 'Status change notification message', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('game_108_description', '🎯 <b>Трансформационная игра «108»</b>\n\nГотов(а) заглянуть вглубь себя?', 'html', 'general', 'Game 108 description', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('question_prompt', '🕊 <b>Как ты хочешь задать вопрос?</b>', 'html', 'general', 'Question type selection prompt', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """)


def downgrade() -> None:
    op.drop_table('menu_buttons')
    op.drop_index(op.f('ix_dynamic_content_key'), table_name='dynamic_content')
    op.drop_table('dynamic_content')
    op.drop_column('roles', 'permissions')
