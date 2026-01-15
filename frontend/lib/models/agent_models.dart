class Activity {
  final String id;
  final String name;
  final String? color;

  Activity({required this.id, required this.name, this.color});

  factory Activity.fromJson(Map<String, dynamic> json) {
    return Activity(
      id: json['id'] as String,
      name: json['name'] as String,
      color: json['color'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'color': color,
  };
}

class Employment {
  final String id;
  final String name;
  final String role;
  final int? contractHours;

  Employment({
    required this.id, 
    required this.name, 
    required this.role,
    this.contractHours,
  });

  // Getter for compatibility with existing UI that might check emp.roles.isNotEmpty
  List<String> get roles => [role];

  factory Employment.fromJson(Map<String, dynamic> json) {
    return Employment(
      id: json['id'] as String,
      name: json['name'] as String,
      role: json['role'] as String? ?? (json['roles'] != null && (json['roles'] as List).isNotEmpty ? json['roles'][0] : "worker"),
      contractHours: json['contract_hours'] as int?,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'role': role,
    'contract_hours': contractHours,
  };
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
      id: json['id'] as String?,
      employeeId: json['employee_id'] as String,
      activityId: json['activity_id'] as String,
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

  const DemandConfig({
    this.weekdayTarget = 3,
    this.weekendTarget = 2,
    this.aiEnabled = true,
  });

  factory DemandConfig.fromJson(Map<String, dynamic> json) {
    return DemandConfig(
      weekdayTarget: json['weekdayTarget'] ?? 3,
      weekendTarget: json['weekendTarget'] ?? 2,
      aiEnabled: json['aiEnabled'] ?? true,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'weekdayTarget': weekdayTarget,
      'weekendTarget': weekendTarget,
      'aiEnabled': aiEnabled,
    };
  }

  DemandConfig copyWith({
    int? weekdayTarget,
    int? weekendTarget,
    bool? aiEnabled,
  }) {
    return DemandConfig(
      weekdayTarget: weekdayTarget ?? this.weekdayTarget,
      weekendTarget: weekendTarget ?? this.weekendTarget,
      aiEnabled: aiEnabled ?? this.aiEnabled,
    );
  }
}
