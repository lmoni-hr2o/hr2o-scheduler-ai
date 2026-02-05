import 'package:cloud_firestore/cloud_firestore.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../utils/security_utils.dart';
import '../models/agent_models.dart';
import '../models/company_model.dart';

class ScheduleRepository {
  final FirebaseFirestore _firestore;
  
  // USE THIS FOR LOCAL DEV:
  //static const String _baseUrl = "http://127.0.0.1:8000";
  
  // USE THIS FOR PRODUCTION:
  static const String _baseUrl = "https://timeplanner-466805262752.europe-west3.run.app";

  ScheduleRepository({FirebaseFirestore? firestore, String? companyId})
      : _firestore = firestore ?? FirebaseFirestore.instance;

  String get _currentEnv => SecurityUtils.activeEnvironment;
  
  /// Sanitizes company ID for use in Firestore paths (removes slashes)
  String get _sanitizedEnv => SecurityUtils.activeEnvironment.replaceAll('/', '_');

  Future<List<Activity>> getActivities() async {
    final url = Uri.parse("$_baseUrl/agent/activities");
    final response = await http.get(url, headers: SecurityUtils.getHeaders(""));
    
    if (response.statusCode == 200) {
      final List data = jsonDecode(response.body);
      return data.map((item) => Activity.fromJson(item)).toList();
    }
    throw Exception("Failed to load activities: ${response.body}");
  }

  Future<List<Employment>> getEmployment() async {
    final url = Uri.parse("$_baseUrl/agent/employment");
    final response = await http.get(url, headers: SecurityUtils.getHeaders(""));
    
    if (response.statusCode == 200) {
      final List data = jsonDecode(response.body);
      return data.map((item) => Employment.fromJson(item)).toList();
    }
    throw Exception("Failed to load employment: ${response.body}");
  }

  Future<List<Company>> getCompanies() async {
    final url = Uri.parse("$_baseUrl/agent/companies");
    final response = await http.get(url, headers: SecurityUtils.getHeaders(""));
    
    if (response.statusCode == 200) {
      final List data = jsonDecode(response.body);
      return data.map((item) => Company.fromJson(item)).toList();
    }
    throw Exception("Failed to load companies: ${response.body}");
  }

  Stream<List<Map<String, dynamic>>> getSchedules() {
    return _firestore
        .collection('companies')
        .doc(_sanitizedEnv)
        .collection('schedules')
        .snapshots()
        .map((snapshot) {
      return snapshot.docs.map((doc) => doc.data()).toList();
    });
  }

  Future<Map<String, dynamic>> getPreCheckAnalysis({
    required List<Employment> employees,
    required List<Activity> activities,
    required Map<String, dynamic> config,
    required DateTime startDate,
    required DateTime endDate,
  }) async {
    // Richiesta a Gemini per analizzare i parametri prima della generazione effettiva
    final payload = {
      "environment": _currentEnv,
      "employees": employees.map((e) => e.toJson()).toList(),
      "activities": activities.map((a) => a.toJson()).toList(),
      "constraints": {"min_rest_hours": 11},
      "config": config,
      "start_date": startDate.toIso8601String().split('T')[0],
      "end_date": endDate.toIso8601String().split('T')[0],
    };

    final jsonPayload = jsonEncode(payload);
    final url = Uri.parse("$_baseUrl/reports/pre-check");

    try {
      final response = await http.post(
        url,
        headers: SecurityUtils.getHeaders(jsonPayload),
        body: jsonPayload,
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      throw Exception("Failed to get pre-check analysis: ${response.body}");
    } catch (e) {
      print("Pre-check error: $e");
      return {
        "summary": "Analisi non disponibile.",
        "suggestions": []
      };
    }
  }

  Future<Map<String, dynamic>> triggerGeneration({
    required DateTime startDate, 
    required DateTime endDate,
    required List<Employment> employees,
    required List<Activity> activities,
    List<Map<String, dynamic>> requiredShifts = const [],
    List<Map<String, dynamic>> unavailabilities = const [],
    Map<String, dynamic> constraints = const {},
  }) async {
    // Note: We send empty lists for employees/activities to check if backend handles fetch
    // But if backend expects data, we should send it.
    // The previous code sent empty lists. We keep it as is, assuming backend pulls from DB.
    final payload = {
      "start_date": startDate.toIso8601String().split('T')[0],
      "end_date": endDate.toIso8601String().split('T')[0],
      "employees": employees.map((e) => e.toJson()).toList(), // Use actual data to ensure Worker has it
      "required_shifts": requiredShifts,
      "unavailabilities": unavailabilities,
      "activities": activities.map((a) => a.toJson()).toList(), 
      "constraints": {
        "min_rest_hours": 11,
        ...constraints
      }
    };

    final payloadStr = jsonEncode(payload);
    final url = Uri.parse("$_baseUrl/schedule/generate");
    
    try {
      // 1. Start Job
      print("Starting async schedule generation...");
      final response = await http.post(
        url,
        headers: SecurityUtils.getHeaders(payloadStr),
        body: payloadStr,
      );

      if (response.statusCode != 200) {
        throw Exception("Failed to start generation: ${response.body}");
      }

      final jobData = jsonDecode(response.body);
      final jobId = jobData['job_id'];
      print("Job started: $jobId. Polling for results...");

      // 2. Poll for Completion
      int attempts = 0;
      // Poll for up to 20 minutes (600 * 2s = 1200s)
      while (attempts < 600) { 
         await Future.delayed(Duration(seconds: 2));
         
         final statusUrl = Uri.parse("$_baseUrl/schedule/job/$jobId");
         final statusResp = await http.get(statusUrl, headers: SecurityUtils.getHeaders(""));
         
         if (statusResp.statusCode == 200) {
             final statusData = jsonDecode(statusResp.body);
             final status = statusData['status'];
             
             if (status == 'completed') {
                 print("Job completed!");
                 return statusData; // Contains 'schedule' and 'solver_status'
             }
             if (status == 'failed') {
                 throw Exception("Job failed: ${statusData['error']}");
             }
             // If 'queued' or 'processing', continue loop
         }
         attempts++;
      }
      throw Exception("Timeout waiting for schedule generation (5 mins)");

    } catch (e) {
      print("Error calling Cloud Run: $e");
      rethrow;
    }
  }


  Future<Map<String, dynamic>> retrain() async {
    final url = Uri.parse("$_baseUrl/training/retrain");
    final payloadStr = jsonEncode({"company_id": _currentEnv});
    
    try {
      final response = await http.post(
        url,
        headers: SecurityUtils.getHeaders(payloadStr),
        body: payloadStr,
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception("Retraining failed: ${response.body}");
      }
    } catch (e) {
      print("Error calling Retrain API: $e");
      rethrow;
    }
  }

  Future<Map<String, dynamic>> getDiagnostics() async {
    final url = Uri.parse("$_baseUrl/agent/diagnostics");
    try {
      final response = await http.get(url, headers: SecurityUtils.getHeaders(""));
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      return {};
    } catch (e) {
      print("Error getting diagnostics: $e");
      return {};
    }
  }

  Future<Map<String, List<String>>> getSchema() async {
    final response = await http.get(
      Uri.parse('$_baseUrl/agent/schema'),
      headers: SecurityUtils.getHeaders(""),
    );
    if (response.statusCode != 200) return {};
    final data = json.decode(response.body) as Map<String, dynamic>;
    return data.map((key, value) => MapEntry(key, List<String>.from(value)));
  }

  Future<List<Map<String, dynamic>>> getFeatures() async {
    final response = await http.get(
      Uri.parse('$_baseUrl/agent/features'),
      headers: SecurityUtils.getHeaders(""),
    );
    if (response.statusCode != 200) return [];
    final List<dynamic> data = json.decode(response.body);
    return data.map((e) => e as Map<String, dynamic>).toList();
  }

  Future<Map<String, List<String>>> getMappings() async {
    final response = await http.get(
      Uri.parse('$_baseUrl/agent/mappings'),
      headers: SecurityUtils.getHeaders(""),
    );
    if (response.statusCode != 200) return {};
    final data = json.decode(response.body) as Map<String, dynamic>;
    return data.map((key, value) => MapEntry(key, List<String>.from(value)));
  }

  Future<void> saveMappings(Map<String, List<String>> mappings) async {
    final payloadStr = jsonEncode(mappings);
    final response = await http.post(
      Uri.parse('$_baseUrl/agent/mappings'),
      headers: SecurityUtils.getHeaders(payloadStr),
      body: payloadStr,
    );
    if (response.statusCode != 200) {
      throw Exception("Failed to save mappings: ${response.body}");
    }
  }

  Future<void> downloadReport(String format, List<dynamic> scheduleData) async {
    final url = Uri.parse("$_baseUrl/reports/export-$format");
    final payloadStr = jsonEncode(scheduleData);
    
    try {
      final response = await http.post(
        url,
        headers: SecurityUtils.getHeaders(payloadStr),
        body: payloadStr,
      );

      if (response.statusCode == 200) {
        print("Report generated successfully: ${response.headers['content-disposition']}");
      } else {
        throw Exception("Report generation failed: ${response.body}");
      }
    } catch (e) {
      print("Error downloading report: $e");
      rethrow;
    }
  }

  Future<Map<String, dynamic>> learnDemand() async {
    final url = Uri.parse("$_baseUrl/learning/demand");
    try {
      final response = await http.get(url, headers: SecurityUtils.getHeaders(""));
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      return {};
    } catch (e) {
      print("Error learning demand: $e");
      return {};
    }
  }

  Future<Map<String, dynamic>> getTrainingProgress() async {
    final url = Uri.parse("$_baseUrl/training/progress");
    try {
      final response = await http.get(url, headers: SecurityUtils.getHeaders(""));
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception("Failed to get progress: ${response.body}");
      }
    } catch (e) {
      print("Error fetching progress: $e");
      return {"status": "error", "progress": 0.0, "message": "Connection error"};
    }
  }

  Future<List<Map<String, String>>> getEnvironments() async {
    final url = Uri.parse("$_baseUrl/training/environments");
    try {
      final response = await http.get(url, headers: SecurityUtils.getHeaders(""));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final List envs = data['environments'] ?? [];
        return envs.map((e) => {
          "id": e['id'].toString(),
          "name": e['name'].toString(),
        }).toList();
      }
      return [];
    } catch (e) {
      print("Error fetching environments: $e");
      return [];
    }
  }

  Future<Map<String, dynamic>> getModelStats() async {
    final url = Uri.parse("$_baseUrl/training/model-stats");
    try {
      final response = await http.get(url, headers: SecurityUtils.getHeaders(""));
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      throw Exception("Failed to load model stats");
    } catch (e) {
      print("Error fetching model stats: $e");
      rethrow;
    }
  }

  Future<List<LaborProfile>> getLaborProfiles() async {
    final url = Uri.parse("$_baseUrl/labor-profiles/$_sanitizedEnv");
    try {
      final response = await http.get(url, headers: SecurityUtils.getHeaders(""));
      if (response.statusCode == 200) {
        final List data = jsonDecode(response.body);
        return data.map((e) => LaborProfile.fromJson(e)).toList();
      }
      return [];
    } catch (e) {
      print("Error fetching labor profiles: $e");
      return [];
    }
  }

  Future<Map<String, dynamic>> getAlgorithmConfig() async {
    final url = Uri.parse("$_baseUrl/training/config");
    try {
      final response = await http.get(url, headers: SecurityUtils.getHeaders(""));
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      throw Exception("Failed to load config");
    } catch (e) {
      print("Error fetching algorithm config: $e");
      rethrow;
    }
  }

  Future<void> saveAlgorithmConfig(Map<String, dynamic> config) async {
    final url = Uri.parse("$_baseUrl/training/config");
    final payloadStr = jsonEncode(config);
    try {
      final response = await http.post(
        url,
        headers: SecurityUtils.getHeaders(payloadStr),
        body: payloadStr,
      );
      if (response.statusCode != 200) {
        throw Exception("Failed to save config: ${response.body}");
      }
    } catch (e) {
      print("Error saving algorithm config: $e");
      rethrow;
    }
  }

  Future<void> logFeedback({
    required String action,
    required String selectedId,
    String? rejectedId,
    Map<String, dynamic> shiftData = const {},
  }) async {
    final url = Uri.parse("$_baseUrl/training/log-feedback");
    final payload = {
      "action": action,
      "selected_id": selectedId,
      "rejected_id": rejectedId,
      "shift_data": shiftData,
    };
    final payloadStr = jsonEncode(payload);

    try {
      await http.post(
        url,
        headers: SecurityUtils.getHeaders(payloadStr),
        body: payloadStr,
      );
    } catch (e) {
      print("Error logging feedback: $e");
    }
  }

  Future<List<dynamic>> getHistoricalSchedule(DateTime start, DateTime end) async {
    final startStr = start.toIso8601String().split('T')[0];
    final endStr = end.toIso8601String().split('T')[0];
    final url = Uri.parse("$_baseUrl/schedule/historical?start_date=$startStr&end_date=$endStr");
    
    try {
      final response = await http.get(url, headers: SecurityUtils.getHeaders(""));
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      return [];
    } catch (e) {
      print("Error fetching historical schedule: $e");
      return [];
    }
  }

  Future<void> saveScheduleToFirestore(Map<String, dynamic> scheduleData) async {
    try {
      final docRef = _firestore
          .collection('companies')
          .doc(_sanitizedEnv)
          .collection('schedules')
          .doc('current');
      
      await docRef.set({
        ...scheduleData,
        'timestamp': FieldValue.serverTimestamp(),
        'environment': _currentEnv,
      });
      
      print("Schedule saved to Firestore for $_currentEnv (sanitized: $_sanitizedEnv)");
    } catch (e) {
      print("Error saving schedule to Firestore: $e");
    }
  }

  Future<void> resetStatus() async {
    final response = await http.post(
      Uri.parse('$_baseUrl/agent/reset_status'),
      headers: SecurityUtils.getHeaders(""),
    );
    if (response.statusCode != 200) {
      throw Exception("Failed to reset status: ${response.body}");
    }
  }
  Future<Map<String, dynamic>> getAiAnalysis(List<dynamic> schedule) async {
    final url = Uri.parse("$_baseUrl/reports/analysis");
    final payload = {
      "environment": _currentEnv,
      "schedule": schedule
    };
    final payloadStr = jsonEncode(payload);

    try {
      final response = await http.post(
        url,
        headers: SecurityUtils.getHeaders(payloadStr),
        body: payloadStr,
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception("Failed to get analysis: ${response.body}");
      }
    } catch (e) {
      print("Error calling AI Analysis: $e");
      rethrow;
    }
  }
  Future<void> submitScheduleFeedback(List<dynamic> schedule) async {
    final url = Uri.parse("$_baseUrl/training/feedback");
    final payload = {
      "environment": _currentEnv,
      "schedule": schedule
    };
    final payloadStr = jsonEncode(payload);

    try {
      final response = await http.post(
        url,
        headers: SecurityUtils.getHeaders(payloadStr),
        body: payloadStr,
      );
      if (response.statusCode != 200) {
        print("Feedback failed: ${response.body}");
      }
    } catch (e) {
      print("Error sending feedback: $e");
    }
  }

  Future<void> syncOriginalSource() async {
    final url = Uri.parse("$_baseUrl/sync/full?namespace=OVERCLEAN");
    try {
      final response = await http.post(url, headers: SecurityUtils.getHeaders(""));
      if (response.statusCode != 200) {
        // Log but don't crash, maybe just warning
        print("Sync warning: ${response.body}");
      }
    } catch (e) {
      print("Error triggering sync: $e");
    }
  }
}
