class Activity {
  final String id;
  final String name;
  final String? color;
  final Map<String, dynamic>? project; // Project/customer info

  Activity({
    required this.id,
    required this.name,
    this.color,
    this.project,
  });

  factory Activity.fromJson(Map<String, dynamic> json) {
    return Activity(
      id: json['id']?.toString() ?? '',
      name: json['name'] as String? ?? 'Unknown Activity',
      color: json['color'] as String?,
      project: json['project'] as Map<String, dynamic>?,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    if (color != null) 'color': color,
    if (project != null) 'project': project,
  };
}

class Employment {
  final String id;
  final String name; // Company Name
  final String fullName; // Person Name
  final String role;
  final int? contractHours;
  final bool hasHistory;
  final List<String> projectIds;
  final List<String> customerKeywords;
  final String? address;
  final String? bornDate;
  final String? laborProfileId;

  Employment({
    required this.id, 
    required this.name, 
    required this.fullName,
    required this.role,
    this.contractHours,
    this.hasHistory = false,
    this.projectIds = const [],
    this.customerKeywords = const [],
    this.address,
    this.bornDate,
    this.laborProfileId,
  });

  List<String> get roles => [role];

  factory Employment.fromJson(Map<String, dynamic> json) {
    return Employment(
      id: json['id']?.toString() ?? '',
      name: json['name'] as String? ?? "Unknown Company",
      fullName: json['fullName'] as String? ?? "Unknown Employee",
      role: json['role'] as String? ?? "worker",
      contractHours: json['contract_hours'] is int 
          ? json['contract_hours'] 
          : int.tryParse(json['contract_hours']?.toString() ?? ''),
      hasHistory: json['has_history'] as bool? ?? false,
      projectIds: (json['project_ids'] as List?)?.map((e) => e.toString()).toList() ?? [],
      customerKeywords: (json['customer_keywords'] as List?)?.map((e) => e.toString()).toList() ?? [],
      address: json['address'] as String?,
      bornDate: json['bornDate'] as String?,
      laborProfileId: json['labor_profile_id']?.toString(),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'fullName': fullName,
    'role': role,
    'contract_hours': contractHours,
    'has_history': hasHistory,
    'project_ids': projectIds,
    'customer_keywords': customerKeywords,
    'address': address,
    'bornDate': bornDate,
    'labor_profile_id': laborProfileId,
  };
}

class LaborProfile {
  final String id;
  final String name;
  final String companyId;
  final double maxWeeklyHours;
  final double maxDailyHours;
  final int maxConsecutiveDays;
  final double minRestHours;
  final bool isDefault;

  LaborProfile({
    required this.id,
    required this.name,
    required this.companyId,
    this.maxWeeklyHours = 40.0,
    this.maxDailyHours = 8.0,
    this.maxConsecutiveDays = 6,
    this.minRestHours = 11.0,
    this.isDefault = false,
  });

  factory LaborProfile.fromJson(Map<String, dynamic> json) {
    return LaborProfile(
      id: json['id']?.toString() ?? '',
      name: json['name'] as String? ?? 'Standard',
      companyId: json['company_id'] as String? ?? '',
      maxWeeklyHours: (json['max_weekly_hours'] as num?)?.toDouble() ?? 40.0,
      maxDailyHours: (json['max_daily_hours'] as num?)?.toDouble() ?? 8.0,
      maxConsecutiveDays: json['max_consecutive_days'] as int? ?? 6,
      minRestHours: (json['min_rest_hours'] as num?)?.toDouble() ?? 11.0,
      isDefault: json['is_default'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'company_id': companyId,
    'max_weekly_hours': maxWeeklyHours,
    'max_daily_hours': maxDailyHours,
    'max_consecutive_days': maxConsecutiveDays,
    'min_rest_hours': minRestHours,
    'is_default': isDefault,
  };

  LaborProfile copyWith({
    String? name,
    double? maxWeeklyHours,
    double? maxDailyHours,
    int? maxConsecutiveDays,
    double? minRestHours,
    bool? isDefault,
  }) {
    return LaborProfile(
      id: this.id,
      name: name ?? this.name,
      companyId: this.companyId,
      maxWeeklyHours: maxWeeklyHours ?? this.maxWeeklyHours,
      maxDailyHours: maxDailyHours ?? this.maxDailyHours,
      maxConsecutiveDays: maxConsecutiveDays ?? this.maxConsecutiveDays,
      minRestHours: minRestHours ?? this.minRestHours,
      isDefault: isDefault ?? this.isDefault,
    );
  }
}

class Period {
  final String? id;
  final String employeeId;
  final String activityId;
  final DateTime tmregister;
  final DateTime tmentry;
  final DateTime tmexit;

  Period({
    this.id,
    required this.employeeId,
    required this.activityId,
    required this.tmregister,
    required this.tmentry,
    required this.tmexit,
  });

  factory Period.fromJson(Map<String, dynamic> json) {
    return Period(
      id: json['id']?.toString(),
      employeeId: json['employee_id']?.toString() ?? '',
      activityId: json['activity_id']?.toString() ?? '',
      tmregister: DateTime.parse(json['tmregister']),
      tmentry: DateTime.parse(json['tmentry']),
      tmexit: DateTime.parse(json['tmexit']),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'employee_id': employeeId,
    'activity_id': activityId,
    'tmregister': tmregister.toIso8601String(),
    'tmentry': tmentry.toIso8601String(),
    'tmexit': tmexit.toIso8601String(),
  };
}

class DemandConfig {
  final int weekdayTarget;
  final int weekendTarget;
  final bool aiEnabled;
  final Map<String, dynamic>? profile;

  const DemandConfig({
    this.weekdayTarget = 3,
    this.weekendTarget = 2,
    this.aiEnabled = true,
    this.profile,
  });

  factory DemandConfig.fromJson(Map<String, dynamic> json) {
    int parseSafe(dynamic v, int def) {
      if (v is int) return v;
      if (v is String) return int.tryParse(v) ?? def;
      return def;
    }

    return DemandConfig(
      weekdayTarget: parseSafe(json['weekdayTarget'], 3),
      weekendTarget: parseSafe(json['weekendTarget'], 2),
      aiEnabled: json['aiEnabled'] ?? true,
      profile: json['profile'] as Map<String, dynamic>?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'weekdayTarget': weekdayTarget,
      'weekendTarget': weekendTarget,
      'aiEnabled': aiEnabled,
      if (profile != null) 'profile': profile,
    };
  }

  DemandConfig copyWith({
    int? weekdayTarget,
    int? weekendTarget,
    bool? aiEnabled,
    Map<String, dynamic>? profile,
  }) {
    return DemandConfig(
      weekdayTarget: weekdayTarget ?? this.weekdayTarget,
      weekendTarget: weekendTarget ?? this.weekendTarget,
      aiEnabled: aiEnabled ?? this.aiEnabled,
      profile: profile ?? this.profile,
    );
  }
}
