// Explicit Editor-only qualification helper. Never enters Play mode or saves the scene.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace RoboRacer.Qualification
{
    public static class NativeTrackRecovery
    {
        [Serializable] private sealed class Input
        {
            public int formatVersion;
            public string normalAuthoring;
            public string assetDirectory;
            public string sourceCommit;
            public Track[] tracks;
        }
        [Serializable] private sealed class Box
        {
            public float[] center;
            public float[] extents;
            public Bounds ToBounds() { return new Bounds(V3(center), 2 * V3(extents)); }
        }
        [Serializable] private sealed class Part
        {
            public int indexStart, indexCount, baseVertex, firstVertex, vertexCount, topology;
            public Box bounds;
            public SubMeshDescriptor Descriptor()
            {
                return new SubMeshDescriptor(indexStart, indexCount, (MeshTopology)topology)
                { baseVertex = baseVertex, firstVertex = firstVertex, vertexCount = vertexCount,
                    bounds = bounds.ToBounds() };
            }
        }
        [Serializable] private sealed class Scalar
        {
            public string name;
            public bool boolean;
            public int value;
        }
        [Serializable] private sealed class VectorSetting { public string name; public float[] value; }
        [Serializable] private sealed class VertexChannel { public int stream, offset, format, dimension; }
        [Serializable] private sealed class Track
        {
            public string name, meshName, vertexFile, indexFile, vertexSha256, indexSha256;
            public int vertexCount, indexCount, layer, colliderCookingOptions;
            public bool isReadable, keepVertices, keepIndices, active;
            public Box bounds;
            public Part[] submeshes;
            public string[] materialPaths, materialSha256;
            public Scalar[] scalarSettings;
            public VectorSetting[] vectorSettings;
            public VertexChannel[] vertexChannels;
            public float[] localPosition, localScale;
        }
        [Serializable] private sealed class TrackResult
        {
            public string name, meshGuid, prefabGuid, meshLocalId, gameObjectLocalId, transformLocalId;
            public string vertexSha256, indexSha256, capturedVertexSha256;
            public int vertexCount, indexCount, vertexStride;
            public bool readable, meshPassed, prefabPassed, scenePassed;
        }
        [Serializable] private sealed class Report
        {
            public string operation, editorVersion, inputSha256, error;
            public bool passed;
            public TrackResult[] tracks;
            public string[] dependencies;
            public string packingBundleDirectory;
            public bool packingTemporaryAssetsRemoved;
        }

        private static void Require(bool value, string message)
        { if (!value) throw new InvalidDataException(message); }
        private static Vector3 V3(float[] v) { return new Vector3(v[0], v[1], v[2]); }
        private static Vector4 V4(float[] v) { return new Vector4(v[0], v[1], v[2], v[3]); }
        private static string Hash(byte[] data)
        { using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(data)).Replace("-", "").ToLowerInvariant(); }
        private static string Arg(string name)
        {
            var args = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(args, name);
            if (i < 0 || i + 1 >= args.Length) throw new ArgumentException("Missing " + name);
            return args[i + 1];
        }
        private static string MeshPath(Input input, Track t) { return input.assetDirectory + "/" + t.name + ".asset"; }
        private static string PrefabPath(Input input, Track t) { return input.assetDirectory + "/" + t.name + ".prefab"; }
        private static SerializedProperty Property(SerializedObject obj, string name)
        {
            var p = obj.FindProperty(name);
            Require(p != null, "Missing serialized property " + name);
            return p;
        }
        private static void ChannelMetadata(Mesh mesh, Track t, bool apply, bool authoring = false)
        {
            // Preserve captured serialized bytes, including upper dimension bits.
            // Do not infer that undocumented bits are irrelevant to the player.
            Require(t.vertexChannels != null && t.vertexChannels.Length == 14,
                "Captured full channel metadata is required");
            var obj = new SerializedObject(mesh);
            var channels = Property(obj, "m_VertexData.m_Channels");
            Require(channels.arraySize == t.vertexChannels.Length, "Channel count differs");
            for (int i = 0; i < t.vertexChannels.Length; i++)
            {
                var expected = t.vertexChannels[i];
                var row = channels.GetArrayElementAtIndex(i);
                var names = new[] { "stream", "offset", "format", "dimension" };
                var values = new[] { expected.stream, expected.offset, expected.format, expected.dimension };
                if (authoring)
                {
                    if (i == 1) { values[2] = 0; values[3] = 3; }
                    if (i == 2) values[1] = 24;
                    if (i == 4) values[1] = 32;
                }
                for (int j = 0; j < names.Length; j++)
                {
                    var p = row.FindPropertyRelative(names[j]);
                    Require(p != null, "Missing channel field " + names[j]);
                    if (apply) p.intValue = values[j];
                    else Require(p.intValue == values[j], t.name + " serialized channel mismatch " + i + "/" + names[j]);
                }
            }
            if (apply) obj.ApplyModifiedPropertiesWithoutUndo();
        }
        private static void RendererSettings(MeshRenderer renderer, Track t, bool apply)
        {
            var obj = new SerializedObject(renderer);
            foreach (var s in t.scalarSettings)
            {
                if (s.name == "m_LightmapIndex" || s.name == "m_LightmapIndexDynamic")
                {
                    // Player-only ushort fields: no lightmap is authored for these tracks.
                    int index = s.name == "m_LightmapIndex" ? renderer.lightmapIndex : renderer.realtimeLightmapIndex;
                    Require(s.value == 65535 && (index & 65535) == s.value, "Unexpected track lightmap assignment");
                    continue;
                }
                var p = Property(obj, s.name);
                bool booleanProperty = p.propertyType == SerializedPropertyType.Boolean;
                Require(booleanProperty || p.propertyType == SerializedPropertyType.Integer
                    || p.propertyType == SerializedPropertyType.Enum, "Unexpected renderer scalar type: " + s.name);
                if (apply) { if (booleanProperty) p.boolValue = s.value != 0; else p.intValue = s.value; }
                else Require(booleanProperty ? p.boolValue == (s.value != 0) : p.intValue == s.value,
                    t.name + " renderer mismatch: " + s.name);
            }
            foreach (var s in t.vectorSettings)
            {
                Require(s.name == "m_LightmapTilingOffset" || s.name == "m_LightmapTilingOffsetDynamic",
                    "Unexpected renderer vector field");
                bool dynamic = s.name == "m_LightmapTilingOffsetDynamic";
                if (apply)
                {
                    if (dynamic) renderer.realtimeLightmapScaleOffset = V4(s.value);
                    else renderer.lightmapScaleOffset = V4(s.value);
                }
                else Require((dynamic ? renderer.realtimeLightmapScaleOffset : renderer.lightmapScaleOffset).Equals(V4(s.value)),
                    t.name + " renderer vector: " + s.name);
            }
            if (apply) obj.ApplyModifiedPropertiesWithoutUndo();
            else
            {
                Require(renderer.additionalVertexStreams == null && renderer.probeAnchor == null
                    && renderer.lightProbeProxyVolumeOverride == null && !renderer.isPartOfStaticBatch,
                    "Unexpected renderer stream, probe reference or static batching");
            }
        }
        private static Material[] Materials(Track t)
        {
            Require(t.materialPaths.Length == 2 && t.materialSha256.Length == 2, "Expected two original materials");
            return t.materialPaths.Select((path, i) =>
            {
                Require(Hash(File.ReadAllBytes(path)) == t.materialSha256[i], "Source material changed: " + path);
                var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
                Require(mat != null && mat.shader != null, "Material/shader missing: " + path);
                return mat;
            }).ToArray();
        }
        private static byte[] AuthoringVertices(Track t)
        {
            // Exact half-to-float promotion allows the unchanged Unity build compressor
            // to recreate the captured Float16x4 normal packing and full metadata.
            byte[] raw = File.ReadAllBytes(t.vertexFile);
            Require(BitConverter.IsLittleEndian && raw.Length == t.vertexCount * 32
                && Hash(raw) == t.vertexSha256, "Authoring input buffer mismatch");
            var vertices = new byte[t.vertexCount * 36];
            for (int v = 0; v < t.vertexCount; v++)
            {
                Buffer.BlockCopy(raw, v * 32, vertices, v * 36, 12);
                Require(BitConverter.ToUInt16(raw, v * 32 + 18) == 0,
                    "Cannot drop a nonzero padded normal component");
                for (int c = 0; c < 3; c++)
                {
                    ushort half = BitConverter.ToUInt16(raw, v * 32 + 12 + c * 2);
                    float value = Mathf.HalfToFloat(half);
                    Require(!float.IsNaN(value) && !float.IsInfinity(value)
                        && Mathf.FloatToHalf(value) == half, "Normal promotion is not exact");
                    Buffer.BlockCopy(BitConverter.GetBytes(value), 0, vertices, v * 36 + 12 + c * 4, 4);
                }
                Buffer.BlockCopy(raw, v * 32 + 20, vertices, v * 36 + 24, 12);
            }
            return vertices;
        }
        private static void GenerateOne(Input input, Track t)
        {
            string meshPath = MeshPath(input, t), prefabPath = PrefabPath(input, t);
            Require(!File.Exists(meshPath) && !File.Exists(prefabPath), "Generation never overwrites assets");
            var vertices = AuthoringVertices(t);
            var indices = File.ReadAllBytes(t.indexFile);
            Require(indices.Length == t.indexCount * 4
                && Hash(indices) == t.indexSha256, "Input index buffer mismatch");
            var words = new uint[t.indexCount];
            Buffer.BlockCopy(indices, 0, words, 0, indices.Length);
            Require(words.All(i => i < t.vertexCount), "Invalid input index");
            var mesh = new Mesh { name = t.meshName };
            mesh.SetVertexBufferParams(t.vertexCount,
                new VertexAttributeDescriptor(VertexAttribute.Position, VertexAttributeFormat.Float32, 3),
                new VertexAttributeDescriptor(VertexAttribute.Normal, VertexAttributeFormat.Float32, 3),
                new VertexAttributeDescriptor(VertexAttribute.Tangent, VertexAttributeFormat.Float16, 4),
                new VertexAttributeDescriptor(VertexAttribute.TexCoord0, VertexAttributeFormat.Float16, 2));
            mesh.SetVertexBufferData(vertices, 0, 0, vertices.Length, 0, MeshUpdateFlags.DontRecalculateBounds);
            mesh.SetIndexBufferParams(t.indexCount, IndexFormat.UInt32);
            mesh.SetIndexBufferData(words, 0, 0, words.Length, MeshUpdateFlags.DontRecalculateBounds);
            mesh.subMeshCount = t.submeshes.Length;
            for (int i = 0; i < t.submeshes.Length; i++)
                mesh.SetSubMesh(i, t.submeshes[i].Descriptor(), MeshUpdateFlags.DontRecalculateBounds);
            mesh.bounds = t.bounds.ToBounds();
            // Change persisted CPU-readability flags without discarding the data being serialized.
            var serialized = new SerializedObject(mesh);
            Property(serialized, "m_IsReadable").boolValue = t.isReadable;
            Property(serialized, "m_KeepVertices").boolValue = t.keepVertices;
            Property(serialized, "m_KeepIndices").boolValue = t.keepIndices;
            serialized.ApplyModifiedPropertiesWithoutUndo();
            ChannelMetadata(mesh, t, false, true);
            var root = new GameObject(t.name) { layer = t.layer };
            try
            {
                root.AddComponent<MeshFilter>().sharedMesh = mesh;
                var renderer = root.AddComponent<MeshRenderer>();
                renderer.sharedMaterials = Materials(t);
                RendererSettings(renderer, t, true);
                AssetDatabase.CreateAsset(mesh, meshPath);
                // CreateAsset assigns the filename to the main object; restore captured identity.
                mesh.name = t.meshName;
                EditorUtility.SetDirty(mesh);
                AssetDatabase.SaveAssets();
                bool saved;
                PrefabUtility.SaveAsPrefabAsset(root, prefabPath, out saved);
                Require(saved, "Prefab save failed");
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
            AssetDatabase.SaveAssets();
            AssetDatabase.ImportAsset(meshPath, ImportAssetOptions.ForceUpdate);
            AssetDatabase.ImportAsset(prefabPath, ImportAssetOptions.ForceUpdate);
        }
        private static string Id(UnityEngine.Object value, out string guid)
        {
            long id;
            Require(AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value, out guid, out id), "Missing asset ID");
            return id.ToString(System.Globalization.CultureInfo.InvariantCulture);
        }
        private static TrackResult VerifyOne(Input input, Track t)
        {
            var mesh = AssetDatabase.LoadAssetAtPath<Mesh>(MeshPath(input, t));
            Require(mesh != null, "Native mesh did not reload");
            ChannelMetadata(mesh, t, false, true);
            var r = new TrackResult { name = t.name, vertexCount = mesh.vertexCount,
                vertexStride = mesh.GetVertexBufferStride(0), readable = mesh.isReadable };
            r.meshLocalId = Id(mesh, out r.meshGuid);
            using (var data = MeshUtility.AcquireReadOnlyMeshData(mesh))
            {
                var vertices = data[0].GetVertexData<byte>(0).ToArray();
                var indices = data[0].GetIndexData<byte>().ToArray();
                r.vertexSha256 = Hash(vertices); r.indexSha256 = Hash(indices); r.indexCount = indices.Length / 4;
                r.capturedVertexSha256 = t.vertexSha256;
                Require(r.vertexSha256 == Hash(AuthoringVertices(t)) && r.indexSha256 == t.indexSha256,
                    t.name + " persisted raw buffers differ");
            }
            Require(mesh.name == t.meshName, t.name + " mesh name mismatch: " + mesh.name);
            Require(mesh.vertexCount == t.vertexCount && r.vertexStride == 36
                && mesh.isReadable == t.isReadable && mesh.indexFormat == IndexFormat.UInt32,
                t.name + " mesh vertex/readability/index layout mismatch");
            Require(mesh.bounds.Equals(t.bounds.ToBounds()) && mesh.subMeshCount == t.submeshes.Length,
                t.name + " mesh bounds/submesh count mismatch");
            var expected = new[] {
                new VertexAttributeDescriptor(VertexAttribute.Position, VertexAttributeFormat.Float32, 3),
                new VertexAttributeDescriptor(VertexAttribute.Normal, VertexAttributeFormat.Float32, 3),
                new VertexAttributeDescriptor(VertexAttribute.Tangent, VertexAttributeFormat.Float16, 4),
                new VertexAttributeDescriptor(VertexAttribute.TexCoord0, VertexAttributeFormat.Float16, 2) };
            Require(mesh.GetVertexAttributes().SequenceEqual(expected), t.name + " vertex attributes differ");
            for (int i = 0; i < t.submeshes.Length; i++)
            {
                var a = mesh.GetSubMesh(i); var b = t.submeshes[i].Descriptor();
                Require(a.indexStart == b.indexStart && a.indexCount == b.indexCount && a.baseVertex == b.baseVertex
                    && a.firstVertex == b.firstVertex && a.vertexCount == b.vertexCount && a.topology == b.topology
                    && a.bounds.Equals(b.bounds), t.name + " submesh differs: " + i);
            }
            r.meshPassed = true;
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath(input, t));
            Require(prefab != null && prefab.name == t.name && prefab.transform.childCount == 0
                && prefab.layer == t.layer && prefab.GetComponents<Component>().Length == 3,
                t.name + " prefab object structure mismatch");
            r.gameObjectLocalId = Id(prefab, out r.prefabGuid);
            string ignored;
            r.transformLocalId = Id(prefab.transform, out ignored);
            Require(prefab.GetComponent<MeshFilter>().sharedMesh == mesh, "Prefab mesh mismatch");
            var renderer = prefab.GetComponent<MeshRenderer>();
            Require(renderer.sharedMaterials.SequenceEqual(Materials(t)), "Prefab material order mismatch");
            RendererSettings(renderer, t, false);
            r.prefabPassed = true;
            return r;
        }
        private static void VerifyScene(Input input, Report report)
        {
            const string path = "Assets/Scenes/F1TENTH.unity";
            var scene = EditorSceneManager.OpenScene(path, OpenSceneMode.Additive);
            try
            {
                var all = scene.GetRootGameObjects().SelectMany(root => root.GetComponentsInChildren<Transform>(true)).ToArray();
                foreach (var t in input.tracks)
                {
                    var matches = all.Where(x => x.name == t.name && x.parent != null && x.parent.name == "Infrastructure").ToArray();
                    Require(matches.Length == 1, "Track missing or duplicated: " + t.name);
                    var tr = matches[0]; var go = tr.gameObject;
                    Require(tr.localPosition.Equals(V3(t.localPosition)) && tr.localScale.Equals(V3(t.localScale))
                        && tr.localRotation.Equals(Quaternion.identity) && go.activeSelf == t.active
                        && go.layer == t.layer && tr.childCount == 0, "Scene track transform/activation mismatch: " + t.name);
                    var mesh = AssetDatabase.LoadAssetAtPath<Mesh>(MeshPath(input, t));
                    var collider = go.GetComponent<MeshCollider>();
                    Require(collider != null && collider.sharedMesh == mesh && collider.enabled
                        && !collider.convex && !collider.isTrigger && collider.sharedMaterial == null
                        && (int)collider.cookingOptions == t.colliderCookingOptions
                        && go.GetComponent<MeshFilter>().sharedMesh == mesh, "Scene collider/mesh mismatch");
                    var renderer = go.GetComponent<MeshRenderer>();
                    Require(renderer.sharedMaterials.SequenceEqual(Materials(t)), "Scene materials differ");
                    RendererSettings(renderer, t, false);
                    report.tracks.Single(r => r.name == t.name).scenePassed = true;
                }
                foreach (var tr in all)
                    Require(tr.GetComponents<Component>().All(c => c != null), "Missing scene component: " + tr.name);
                report.dependencies = AssetDatabase.GetDependencies(path, true).OrderBy(x => x, StringComparer.Ordinal).ToArray();
                Require(!report.dependencies.Any(p => p.EndsWith(".skp", StringComparison.OrdinalIgnoreCase)),
                    "Required scene still depends on SketchUp");
            }
            finally { EditorSceneManager.CloseScene(scene, true); }
        }
        private static void ProbePacking(Input input, Report report, string reportPath)
        {
            // Explicit diagnostic only. Existing track assets and scene are never written.
            const string directory = "Assets/RoboRacerQualification/PackingProbe";
            Require(AssetDatabase.IsValidFolder("Assets/RoboRacerQualification")
                && !Directory.Exists(directory) && !File.Exists(directory + ".meta"),
                "Packing probe requires a fresh owned directory in an existing recovery copy");
            var paths = new List<string>();
            AssetDatabase.CreateFolder("Assets/RoboRacerQualification", "PackingProbe");
            try
            {
                foreach (var t in input.tracks)
                foreach (bool floatNormal in new[] { false, true })
                {
                    byte[] raw = File.ReadAllBytes(t.vertexFile), indices = File.ReadAllBytes(t.indexFile);
                    Require(raw.Length == t.vertexCount * 32 && Hash(raw) == t.vertexSha256
                        && indices.Length == t.indexCount * 4 && Hash(indices) == t.indexSha256,
                        "Packing probe input buffers changed");
                    byte[] vertices = raw;
                    if (floatNormal)
                    {
                        vertices = AuthoringVertices(t);
                    }
                    var mesh = new Mesh();
                    mesh.SetVertexBufferParams(t.vertexCount,
                        new VertexAttributeDescriptor(VertexAttribute.Position, VertexAttributeFormat.Float32, 3),
                        new VertexAttributeDescriptor(VertexAttribute.Normal,
                            floatNormal ? VertexAttributeFormat.Float32 : VertexAttributeFormat.Float16, floatNormal ? 3 : 4),
                        new VertexAttributeDescriptor(VertexAttribute.Tangent, VertexAttributeFormat.Float16, 4),
                        new VertexAttributeDescriptor(VertexAttribute.TexCoord0, VertexAttributeFormat.Float16, 2));
                    mesh.SetVertexBufferData(vertices, 0, 0, vertices.Length, 0, MeshUpdateFlags.DontRecalculateBounds);
                    var words = new uint[t.indexCount];
                    Buffer.BlockCopy(indices, 0, words, 0, indices.Length);
                    mesh.SetIndexBufferParams(t.indexCount, IndexFormat.UInt32);
                    mesh.SetIndexBufferData(words, 0, 0, words.Length, MeshUpdateFlags.DontRecalculateBounds);
                    mesh.subMeshCount = t.submeshes.Length;
                    for (int i = 0; i < t.submeshes.Length; i++)
                        mesh.SetSubMesh(i, t.submeshes[i].Descriptor(), MeshUpdateFlags.DontRecalculateBounds);
                    mesh.bounds = t.bounds.ToBounds();
                    var obj = new SerializedObject(mesh);
                    Property(obj, "m_IsReadable").boolValue = false;
                    Property(obj, "m_KeepVertices").boolValue = false;
                    Property(obj, "m_KeepIndices").boolValue = false;
                    obj.ApplyModifiedPropertiesWithoutUndo();
                    if (!floatNormal) ChannelMetadata(mesh, t, true);
                    string path = directory + "/" + t.name + (floatNormal ? "-float-normal" : "-captured-half") + ".asset";
                    AssetDatabase.CreateAsset(mesh, path);
                    paths.Add(path);
                }
                AssetDatabase.SaveAssets();
                report.packingBundleDirectory = Path.Combine(Path.GetDirectoryName(reportPath), "packing-bundles");
                Require(!Directory.Exists(report.packingBundleDirectory), "Packing bundle output already exists");
                Directory.CreateDirectory(report.packingBundleDirectory);
                var bundle = new AssetBundleBuild { assetBundleName = "track-packing", assetNames = paths.ToArray() };
                Require(BuildPipeline.BuildAssetBundles(report.packingBundleDirectory, new[] { bundle },
                    BuildAssetBundleOptions.UncompressedAssetBundle | BuildAssetBundleOptions.StrictMode,
                    BuildTarget.StandaloneLinux64) != null, "Packing bundle build failed");
            }
            finally
            {
                // Only this invocation's fresh temporary folder; all output remains in results.
                report.packingTemporaryAssetsRemoved = AssetDatabase.DeleteAsset(directory)
                    && !Directory.Exists(directory) && !File.Exists(directory + ".meta");
            }
            Require(report.packingTemporaryAssetsRemoved, "Packing probe cleanup failed");
        }
        public static void Run()
        {
            string inputPath = Arg("-roboracerTrackInputs"), outputPath = Arg("-roboracerTrackReport");
            var report = new Report { operation = Arg("-roboracerTrackMode"), editorVersion = Application.unityVersion,
                inputSha256 = Hash(File.ReadAllBytes(inputPath)) };
            var results = new List<TrackResult>();
            try
            {
                var input = JsonUtility.FromJson<Input>(File.ReadAllText(inputPath));
                Require(Application.unityVersion == "2021.3.9f1"
                    && (input.formatVersion == 2 && input.normalAuthoring == "float32x3"
                        || report.operation == "packing-probe" && input.formatVersion == 1)
                    && input.sourceCommit == "635dbb6d86ec98e25ea845a97188f7bbe85a09e8"
                    && input.assetDirectory == "Assets/RoboRacerQualification/Tracks"
                    && input.tracks.Select(t => t.name).OrderBy(n => n).SequenceEqual(new[] { "Berlin Track", "Proto Track" }),
                    "Unexpected Editor/input/scope");
                if (report.operation == "packing-probe")
                {
                    ProbePacking(input, report, outputPath);
                    report.passed = true;
                    return;
                }
                if (report.operation == "generate")
                {
                    Require(!Directory.Exists(input.assetDirectory), "Native asset directory must be fresh");
                    if (!AssetDatabase.IsValidFolder("Assets/RoboRacerQualification"))
                        AssetDatabase.CreateFolder("Assets", "RoboRacerQualification");
                    AssetDatabase.CreateFolder("Assets/RoboRacerQualification", "Tracks");
                    foreach (var t in input.tracks) GenerateOne(input, t);
                }
                else Require(report.operation == "verify", "Unsupported operation");
                foreach (var t in input.tracks) results.Add(VerifyOne(input, t));
                report.tracks = results.ToArray();
                if (report.operation == "verify") VerifyScene(input, report);
                report.passed = true;
            }
            catch (Exception e) { report.error = e.ToString(); throw; }
            finally
            {
                report.tracks = results.ToArray();
                File.WriteAllText(outputPath, JsonUtility.ToJson(report, true));
            }
            Debug.Log("RoboRacer native track " + report.operation + " passed");
        }
    }
}
