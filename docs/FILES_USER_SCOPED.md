# File User-Scoped Architecture

## Overview

Files in Knowledge Navigator are **user-scoped**, meaning they belong to the user and are available across all their sessions, not tied to a specific session.

## Architecture Changes

### Database Schema

**Before:**
- Files were linked to `session_id` (NOT NULL)
- Files were deleted when session was deleted (cascade)

**After:**
- Files are linked to `user_id` (NOT NULL)
- `session_id` is nullable (optional, for backward compatibility)
- Files persist across sessions
- Files can be explicitly deleted by user

### API Endpoints

#### Upload File
- **Endpoint**: `POST /api/files/upload`
- **Parameters**: 
  - `file`: File to upload (required)
  - `session_id`: Optional query parameter (for backward compatibility)
- **Storage**: Files stored in `uploads/users/{user_id}/`
- **Ownership**: File belongs to authenticated user

#### List Files
- **Endpoint**: `GET /api/files/`
- **Returns**: All files for the authenticated user
- **Scope**: User-scoped (all user's files across all sessions)

#### Get File
- **Endpoint**: `GET /api/files/id/{file_id}`
- **Returns**: File details (if owned by authenticated user)
- **Authorization**: Verifies user ownership

#### Delete File
- **Endpoint**: `DELETE /api/files/id/{file_id}`
- **Authorization**: Verifies user ownership
- **Actions**: 
  - Deletes file from filesystem
  - Removes embeddings from ChromaDB
  - Removes record from database

#### Search Files
- **Endpoint**: `POST /api/files/search`
- **Parameters**: `query` (search text), `n_results` (optional)
- **Scope**: Searches only user's files

### Memory Manager

The `retrieve_file_content()` method has been updated:
- **Parameter**: `user_id` instead of `session_id`
- **Query**: Searches ChromaDB embeddings by `user_id` in metadata
- **Scope**: Retrieves files from all user sessions

### Migration

Migration `add_user_id_to_files`:
1. Adds `user_id` column to `files` table
2. Migrates existing data (gets `user_id` from `session.user_id`)
3. Makes `session_id` nullable
4. Creates indexes for performance (`ix_files_user_id`, `ix_files_user_tenant`)

## Benefits

1. **Persistent Files**: Files remain available across sessions
2. **User Control**: Users can manage their files independently
3. **Better Organization**: Files organized by user, not scattered across sessions
4. **Deletion Control**: Users can explicitly delete files when needed

## Backward Compatibility

- Old endpoint `/api/files/upload/{session_id}` is deprecated but still works
- Old endpoint `/api/files/session/{session_id}` returns user files (backward compatible)
- `session_id` in `files` table is nullable but preserved for historical data

