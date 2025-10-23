#!/bin/bash
# Reset Auralis Database - Fresh Start Script

echo "🔄 Resetting Auralis Database..."
echo ""

# 1. Backup existing database
if [ -f ~/Music/Auralis/auralis_library.db ]; then
    BACKUP_NAME="auralis_library.db.backup.$(date +%Y%m%d_%H%M%S)"
    echo "📦 Backing up existing database to: $BACKUP_NAME"
    mv ~/Music/Auralis/auralis_library.db ~/Music/Auralis/$BACKUP_NAME
    echo "✅ Backup complete"
else
    echo "ℹ️  No existing database found"
fi

echo ""
echo "✨ Database reset complete!"
echo ""
echo "Next steps:"
echo "1. Close the current Auralis window (if open)"
echo "2. Run: ./dist/Auralis-1.0.0.AppImage"
echo "3. You should see an empty library ready for your music"
echo ""
