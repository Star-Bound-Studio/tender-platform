import 'package:dio/dio.dart';
import '../models/models.dart';

class ApiService {
  static const String baseUrl = 'http://localhost:8000/api/v1';
  
  late final Dio _dio;
  String? _token;

  ApiService() {
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 15),
      headers: {'Content-Type': 'application/json'},
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (_token != null) {
          options.headers['Authorization'] = 'Bearer $_token';
        }
        return handler.next(options);
      },
      onError: (error, handler) {
        // TODO: handle 401, refresh token, etc.
        return handler.next(error);
      },
    ));
  }

  void setToken(String token) => _token = token;
  void clearToken() => _token = null;

  // ============================================================
  // TENDERS
  // ============================================================

  Future<TenderListResponse> getTenders({
    String? q,
    String? sourceId,
    String? lawType,
    String? region,
    String? okved,
    double? nmckMin,
    double? nmckMax,
    String? status = 'active',
    int page = 1,
    int perPage = 20,
    String sortBy = 'publish_date',
    String sortOrder = 'desc',
  }) async {
    final params = <String, dynamic>{
      'page': page,
      'per_page': perPage,
      'sort_by': sortBy,
      'sort_order': sortOrder,
    };
    if (q != null && q.isNotEmpty) params['q'] = q;
    if (sourceId != null) params['source_id'] = sourceId;
    if (lawType != null) params['law_type'] = lawType;
    if (region != null) params['region'] = region;
    if (okved != null) params['okved'] = okved;
    if (nmckMin != null) params['nmck_min'] = nmckMin;
    if (nmckMax != null) params['nmck_max'] = nmckMax;
    if (status != null) params['status'] = status;

    final resp = await _dio.get('/tenders', queryParameters: params);
    return TenderListResponse.fromJson(resp.data);
  }

  Future<Tender> getTender(String id) async {
    final resp = await _dio.get('/tenders/$id');
    return Tender.fromJson(resp.data);
  }

  Future<Map<String, dynamic>> getTenderStats() async {
    final resp = await _dio.get('/tenders/stats');
    return resp.data;
  }

  Future<Map<String, dynamic>> searchTendersInstant({
    required String q,
    String? sourceId,
    String? region,
    String? okved,
    int page = 1,
    int perPage = 20,
  }) async {
    final params = <String, dynamic>{
      'q': q, 'page': page, 'per_page': perPage,
    };
    if (sourceId != null) params['source_id'] = sourceId;
    if (region != null) params['region'] = region;
    if (okved != null) params['okved'] = okved;

    final resp = await _dio.get('/tenders/search/instant', queryParameters: params);
    return resp.data;
  }

  // ============================================================
  // COMPANIES
  // ============================================================

  Future<Map<String, dynamic>> getCompanies({
    String? q,
    String? okved,
    String? region,
    String? companyType,
    bool? hasSro,
    int page = 1,
    int perPage = 20,
    String sortBy = 'tender_wins_count',
  }) async {
    final params = <String, dynamic>{
      'page': page, 'per_page': perPage, 'sort_by': sortBy,
    };
    if (q != null && q.isNotEmpty) params['q'] = q;
    if (okved != null) params['okved'] = okved;
    if (region != null) params['region'] = region;
    if (companyType != null) params['company_type'] = companyType;
    if (hasSro != null) params['has_sro'] = hasSro;

    final resp = await _dio.get('/companies', queryParameters: params);
    return resp.data;
  }

  Future<Company> getCompany(String inn) async {
    final resp = await _dio.get('/companies/$inn');
    return Company.fromJson(resp.data);
  }

  Future<Map<String, dynamic>> getCompanyTenders(String inn) async {
    final resp = await _dio.get('/companies/$inn/tenders');
    return resp.data;
  }

  // ============================================================
  // REQUESTS
  // ============================================================

  Future<Map<String, dynamic>> getRequests({
    String? q,
    String? region,
    String? category,
    int page = 1,
    int perPage = 20,
  }) async {
    final params = <String, dynamic>{'page': page, 'per_page': perPage};
    if (q != null) params['q'] = q;
    if (region != null) params['region'] = region;
    if (category != null) params['category'] = category;

    final resp = await _dio.get('/requests', queryParameters: params);
    return resp.data;
  }

  Future<SubcontractRequest> createRequest(Map<String, dynamic> data) async {
    final resp = await _dio.post('/requests', data: data);
    return SubcontractRequest.fromJson(resp.data);
  }

  // ============================================================
  // SOURCES
  // ============================================================

  Future<List<TenderSource>> getSources() async {
    final resp = await _dio.get('/sources');
    return (resp.data as List).map((e) => TenderSource.fromJson(e)).toList();
  }

  // ============================================================
  // OKVED
  // ============================================================

  Future<List<Map<String, dynamic>>> searchOkved(String q) async {
    final resp = await _dio.get('/okved/search', queryParameters: {'q': q});
    return List<Map<String, dynamic>>.from(resp.data);
  }

  // ============================================================
  // AUTH
  // ============================================================

  Future<Map<String, dynamic>> register(String email, String password, {String? fullName}) async {
    final resp = await _dio.post('/auth/register', data: {
      'email': email, 'password': password, if (fullName != null) 'full_name': fullName,
    });
    return resp.data;
  }

  Future<String> login(String email, String password) async {
    final resp = await _dio.post('/auth/login', data: {'email': email, 'password': password});
    final token = resp.data['access_token'];
    setToken(token);
    return token;
  }
}
