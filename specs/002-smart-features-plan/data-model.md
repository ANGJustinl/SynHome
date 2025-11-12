# Data Model: Smart Features Implementation

**Date**: 2025-11-12
**Feature**: Smart Features Implementation Planning
**Phase**: Phase 1 - Design & Contracts

## Core Entities

### User Memory System

#### User
```yaml
User:
  id: string (uuid) - Primary identifier
  household_id: string (uuid) - Household association
  name: string - Display name
  email: string - Contact email
  preferences: object - User preferences
  created_at: datetime
  updated_at: datetime
  is_active: boolean
  permissions: array[string] - Device access permissions
```

#### MemoryEntry
```yaml
MemoryEntry:
  id: string (uuid) - Primary identifier
  user_id: string (uuid) - User reference
  type: enum[episodic, semantic, working] - Memory type
  timestamp: datetime - When the memory was created
  content: object - Memory content
  context: object - Contextual information
  embedding: array[float] - Vector embedding for semantic search
  metadata: object - Additional metadata
  importance_score: float - ML-derived importance (0-1)
  expires_at: datetime - Memory expiration time
  is_compressed: boolean - Whether memory is compressed
```

#### DeviceInteraction
```yaml
DeviceInteraction:
  id: string (uuid) - Primary identifier
  user_id: string (uuid) - User who performed action
  device_id: string - Device identifier
  action: string - Action performed
  parameters: object - Action parameters
  timestamp: datetime - When action occurred
  result: object - Action result
  context: object - Environmental context
  session_id: string - Session identifier
```

### Pattern Recognition

#### Pattern
```yaml
Pattern:
  id: string (uuid) - Primary identifier
  user_id: string (uuid) - User this pattern belongs to
  household_id: string (uuid) - Household pattern
  type: enum[temporal, device_combination, conditional] - Pattern type
  name: string - Human readable name
  description: string - Pattern description
  confidence: float - Pattern confidence score (0-1)
  frequency: integer - How often this pattern occurs
  conditions: array[object] - Pattern conditions
  actions: array[object] - Pattern actions
  time_constraints: object - Time-based constraints
  created_at: datetime
  updated_at: datetime
  is_active: boolean
```

#### PatternInstance
```yaml
PatternInstance:
  id: string (uuid) - Primary identifier
  pattern_id: string (uuid) - Pattern reference
  timestamp: datetime - When pattern instance occurred
  matched_conditions: array[object] - Conditions that matched
  deviation_score: float - How much this deviated from expected
  triggered_actions: array[object] - Actions that were triggered
```

### Analytics and Insights

#### AnalyticsEvent
```yaml
AnalyticsEvent:
  id: string (uuid) - Primary identifier
  household_id: string (uuid) - Household reference
  event_type: string - Type of analytics event
  timestamp: datetime - When event occurred
  data: object - Event data
  user_id: string (uuid) - User reference (optional)
  device_id: string - Device reference (optional)
  processed: boolean - Whether processed for insights
```

#### Insight
```yaml
Insight:
  id: string (uuid) - Primary identifier
  household_id: string (uuid) - Household reference
  user_id: string (uuid) - User reference (optional)
  type: enum[energy_saving, usage_pattern, anomaly, recommendation] - Insight type
  title: string - Insight title
  description: string - Detailed description
  impact_score: float - Business/user impact (0-1)
  actionability: enum[informational, suggestion, critical] - Action level
  created_at: datetime
  expires_at: datetime
  is_read: boolean
  is_dismissed: boolean
```

### Remote Control and Sharing

#### RemoteSession
```yaml
RemoteSession:
  id: string (uuid) - Primary identifier
  user_id: string (uuid) - User who owns session
  device_info: object - Device and app information
  ip_address: string - Client IP address
  user_agent: string - Client user agent
  token: string - Session token
  created_at: datetime
  last_activity: datetime
  expires_at: datetime
  is_active: boolean
```

#### SharePermission
```yaml
SharePermission:
  id: string (uuid) - Primary identifier
  owner_id: string (uuid) - User who created share
  shared_with_user_id: string (uuid) - Recipient user (optional)
  share_code: string - Unique share code for temporary access
  device_ids: array[string] - Shared devices
  permissions: array[string] - Permission types (control, view, etc.)
  time_restrictions: object - When access is allowed
  created_at: datetime
  expires_at: datetime
  is_active: boolean
  access_count: integer - How many times accessed
```

## Entity Relationships

```
User (1) -----> (N) MemoryEntry
User (1) -----> (N) DeviceInteraction
User (1) -----> (N) Pattern
User (1) -----> (N) RemoteSession
User (1) -----> (N) SharePermission (as owner)
User (1) -----> (N) SharePermission (as recipient)

Pattern (1) -----> (N) PatternInstance
Household (1) -----> (N) AnalyticsEvent
Household (1) -----> (N) Insight
AnalyticsEvent (1) -----> (N) Insight
```

## Validation Rules

### MemoryEntry Validation
- `type` must be one of: episodic, semantic, working
- `importance_score` must be between 0.0 and 1.0
- `expires_at` must be after `timestamp`
- Working memory entries expire after 24 hours
- Embedding vector length must match configured dimension (384 for sentence transformers)

### Pattern Validation
- `confidence` must be between 0.0 and 1.0
- `frequency` must be positive integer
- At least one condition and one action required
- Time constraints must be valid cron expressions if specified

### AnalyticsEvent Validation
- `event_type` must be from predefined list
- Either `user_id` or `device_id` must be provided
- `data` must be valid JSON object

### SharePermission Validation
- At least one device_id must be specified
- `expires_at` must be after `created_at`
- `share_code` must be unique and at least 16 characters
- Time restrictions must be valid time ranges

## State Transitions

### MemoryEntry States
```
Created → Active → Expired → Archived
   ↓         ↓        ↓        ↓
Working → Compressed → Deleted → Purged
```

### Pattern States
```
Detected → Learning → Active → Inactive → Archived
    ↓         ↓        ↓        ↓        ↓
  New    → Training → Valid → Declining → Forgotten
```

### RemoteSession States
```
Created → Active → Expired → Terminated
    ↓         ↓        ↓         ↓
  Token  → Authenticated → Timeout → Manual Logout
```

## Data Privacy and Security

### Sensitive Data Classification
- **High Sensitivity**: User personal data, authentication tokens, share codes
- **Medium Sensitivity**: Device interaction history, usage patterns
- **Low Sensitivity**: Analytics aggregates, general usage statistics

### Encryption Requirements
- High sensitivity data: AES-256 at rest, TLS 1.3 in transit
- Medium sensitivity data: AES-128 at rest, TLS 1.2 in transit
- Low sensitivity data: Standard encryption

### Retention Policies
- Working memory: 24 hours
- Episodic memory: 30 days (full), 90 days (summarized), 1 year (compressed)
- Remote sessions: 7 days inactive, 30 days total
- Share permissions: Until expiration or revocation
- Analytics events: 1 year aggregated, 90 days raw

## Performance Indexes

### Primary Indexes
- `MemoryEntry.user_id + type + timestamp`
- `Pattern.user_id + is_active + confidence`
- `AnalyticsEvent.household_id + event_type + timestamp`
- `RemoteSession.user_id + is_active + expires_at`

### Secondary Indexes
- `DeviceInteraction.device_id + timestamp`
- `PatternInstance.pattern_id + timestamp`
- `Insight.household_id + is_read + type`
- `SharePermission.share_code + is_active`

### Full-text Search Indexes
- `MemoryEntry.content` (for semantic search)
- `Pattern.description` (for pattern discovery)
- `Insight.title + description` (for insight lookup)

## Data Migration Strategy

### From Current System
1. **Device State Migration**: Import existing device configurations
2. **User Migration**: Create user profiles from current system
3. **Historical Data**: Process existing logs into memory entries
4. **Configuration Migration**: Extend existing YAML configs with memory settings

### Versioning
- Use semantic versioning for schema changes
- Migration scripts for each major version
- Backward compatibility maintained for at least 2 versions
- Data validation during migration process

## Testing Data Requirements

### Unit Testing
- Synthetic user profiles and interactions
- Mock device states and commands
- Sample pattern recognition scenarios
- Test analytics events and insights

### Integration Testing
- Real device configurations
- End-to-end user journeys
- Performance test datasets
- Security penetration test data

### Performance Testing
- Large dataset (10k users, 1M events)
- Concurrent session simulation
- Memory compression performance
- Analytics query performance