import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/agent_models.dart';
import '../utils/security_utils.dart';

class LaborProfileService {
  static const String _baseUrl = "https://timeplanner-466805262752.europe-west3.run.app";

  Future<List<LaborProfile>> getProfiles(String companyId) async {
    final url = Uri.parse("$_baseUrl/labor-profiles/$companyId");
    final response = await http.get(url, headers: SecurityUtils.getHeaders(""));

    if (response.statusCode == 200) {
      final List data = jsonDecode(response.body);
      return data.map((item) => LaborProfile.fromJson(item)).toList();
    }
    throw Exception("Failed to load profiles: ${response.body}");
  }

  Future<LaborProfile> saveProfile(LaborProfile profile) async {
    final url = Uri.parse("$_baseUrl/labor-profiles/");
    final payload = jsonEncode(profile.toJson());
    
    final response = await http.post(
      url,
      headers: SecurityUtils.getHeaders(payload),
      body: payload,
    );

    if (response.statusCode == 200) {
      return LaborProfile.fromJson(jsonDecode(response.body));
    }
    throw Exception("Failed to save profile: ${response.body}");
  }

  Future<void> deleteProfile(String profileId) async {
    final url = Uri.parse("$_baseUrl/labor-profiles/$profileId");
    final response = await http.delete(url, headers: SecurityUtils.getHeaders(""));

    if (response.statusCode != 200) {
      throw Exception("Failed to delete profile: ${response.body}");
    }
  }

  Future<LaborProfile> cloneProfile(String profileId, String targetCompanyId) async {
    final url = Uri.parse("$_baseUrl/labor-profiles/$profileId/clone");
    final payload = jsonEncode({"target_company_id": targetCompanyId});
    
    final response = await http.post(
      url,
      headers: SecurityUtils.getHeaders(payload),
      body: payload,
    );

    if (response.statusCode == 200) {
      return LaborProfile.fromJson(jsonDecode(response.body));
    }
    throw Exception("Failed to clone profile: ${response.body}");
  }

  Future<Map<String, String>> getAssignments(String companyId) async {
    final url = Uri.parse("$_baseUrl/labor-profiles/assignments/$companyId");
    final response = await http.get(url, headers: SecurityUtils.getHeaders(""));

    if (response.statusCode == 200) {
      final Map<String, dynamic> data = jsonDecode(response.body);
      return data.map((key, value) => MapEntry(key, value.toString()));
    }
    throw Exception("Failed to load assignments: ${response.body}");
  }

  Future<void> assignProfile({
    required String employeeId,
    required String? profileId,
    required String companyId,
  }) async {
    final url = Uri.parse("$_baseUrl/labor-profiles/assignments?employee_id=$employeeId&company_id=$companyId" + 
        (profileId != null ? "&profile_id=$profileId" : ""));
    
    final response = await http.post(
      url,
      headers: SecurityUtils.getHeaders(""),
    );

    if (response.statusCode != 200) {
      throw Exception("Failed to assign profile: ${response.body}");
    }
  }
}

