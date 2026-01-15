import 'package:cloud_firestore/cloud_firestore.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../utils/security_utils.dart';
import '../models/agent_models.dart';

class ScheduleRepository {
  final FirebaseFirestore _firestore;
  final String companyId;
  
  // USE THIS FOR LOCAL DEV:
  //static const String _baseUrl = "http://127.0.0.1:8000";
  
  // USE THIS FOR PRODUCTION:
  static const String _baseUrl = "https://timeplanner-466805262752.europe-west3.run.app";

  ScheduleRepository({FirebaseFirestore? firestore, String? companyId})
      : _firestore = firestore ?? FirebaseFirestore.instance,
        companyId = companyId ?? SecurityUtils.activeEnvironment;

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

  Stream<List<Map<String, dynamic>>> getSchedules() {
    return _firestore
        .collection('companies')
        .doc(companyId)
        .collection('schedules')
        .snapshots()
        .map((snapshot) {
      return snapshot.docs.map((doc) => doc.data()).toList();
    });
  }

  Future<Map<String, dynamic>> triggerGeneration({
    required DateTime startDate, 
    required DateTime endDate,
    required List<Employment> employees,
    List<Map<String, dynamic>> unavailabilities = const [],
  }) async {
    final payload = {
      "start_date": startDate.toIso8601String().split('T')[0],
      "end_date": endDate.toIso8601String().split('T')[0],
      "employees": employees.map((e) => e.toJson()).toList(),
      "unavailabilities": unavailabilities,
      "constraints": {"min_rest_hours": 11}
    };

    final payloadStr = jsonEncode(payload);
    final url = Uri.parse("$_baseUrl/schedule/generate");
    
    try {
      final response = await http.post(
        url,
        headers: SecurityUtils.getHeaders(payloadStr),
        body: payloadStr,
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception("Failed to generate: ${response.body}");
      }
    } catch (e) {
      print("Error calling Cloud Run: $e");
      rethrow;
    }
  }

  Future<void> logFeedback({
    required String shiftId,
    required String droppedEmployeeId,
    String? replacedEmployeeId,
    required DateTime shiftStart,
    required String role,
  }) async {
    final url = Uri.parse("$_baseUrl/training/log-feedback");
    
    final payload = {
      "action": "manual_override",
      "selected_id": droppedEmployeeId,
      "rejected_id": replacedEmployeeId,
      "shift_data": {
        "shift_id": shiftId,
        "start": shiftStart.toIso8601String(),
        "role": role
      }
    };

    final payloadStr = jsonEncode(payload);

    try {
      final response = await http.post(
        url,
        headers: SecurityUtils.getHeaders(payloadStr),
        body: payloadStr,
      );

      if (response.statusCode == 200) {
        print("Feedback logged successfully via API for Shift ID: $shiftId");
      } else {
        print("Failed to log feedback: ${response.body}");
      }
    } catch (e) {
      print("Error logging feedback: $e");
    }
  }

  Future<Map<String, dynamic>> triggerRetraining() async {
    final url = Uri.parse("$_baseUrl/training/retrain");
    final payloadStr = jsonEncode({"company_id": companyId});
    
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

  Future<DemandConfig> learnDemand() async {
    // Ensure _baseUrl is accessible. It is likely an instance variable defined at top of class.
    final url = Uri.parse("$_baseUrl/learning/demand");
    try {
      final response = await http.get(url, headers: SecurityUtils.getHeaders(""));
      
      if (response.statusCode == 200) {
        return DemandConfig.fromJson(jsonDecode(response.body));
      } else {
        throw Exception("Failed to learn demand: ${response.body}");
      }
    } catch (e) {
      print("Error learning demand: $e");
      // Fallback to default if offline or error
      return const DemandConfig();
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

  Future<List<String>> getEnvironments() async {
    final url = Uri.parse("$_baseUrl/training/environments");
    try {
      final response = await http.get(url, headers: SecurityUtils.getHeaders(""));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return List<String>.from(data['environments'] ?? []);
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
}
