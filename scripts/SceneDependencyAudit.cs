// Editor-only SIM0 dependency inspection. Never enters Play mode or saves a scene.
using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace RoboRacer.Qualification
{
    public static class SceneDependencyAudit
    {
        [Serializable]
        private sealed class Report
        {
            public string editorVersion;
            public string scene;
            public string[] dependencies;
            public ModelAsset[] modelAssets;
        }

        [Serializable]
        private sealed class ModelAsset
        {
            public string path;
            public bool inSceneDependencies;
            public string importer;
            public string mainAssetType;
            public string[] objectTypes;
            public long[] localFileIds;
        }

        private static ModelAsset InspectModel(string path, string[] dependencies)
        {
            var importer = AssetImporter.GetAtPath(path);
            var main = AssetDatabase.LoadMainAssetAtPath(path);
            var objects = AssetDatabase.LoadAllAssetsAtPath(path)
                .Where(value => value != null).ToArray();
            var ids = objects.Select(value =>
            {
                string guid;
                long id;
                return AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value, out guid, out id) ? id : 0;
            }).ToArray();
            return new ModelAsset
            {
                path = path,
                inSceneDependencies = dependencies.Contains(path),
                importer = importer == null ? null : importer.GetType().FullName,
                mainAssetType = main == null ? null : main.GetType().FullName,
                objectTypes = objects.Select(value => value.GetType().FullName).ToArray(),
                localFileIds = ids
            };
        }

        public static void Run()
        {
            var arguments = Environment.GetCommandLineArgs();
            var index = Array.IndexOf(arguments, "-roboracerSceneAudit");
            if (index < 0 || index + 1 >= arguments.Length)
                throw new ArgumentException("Missing scene audit output path");
            const string scene = "Assets/Scenes/F1TENTH.unity";
            var report = new Report
            {
                editorVersion = Application.unityVersion,
                scene = scene,
                dependencies = AssetDatabase.GetDependencies(scene, true)
                    .OrderBy(path => path, StringComparer.Ordinal).ToArray()
            };
            report.modelAssets = AssetDatabase.GetAllAssetPaths()
                .Where(path => path.EndsWith(".skp", StringComparison.OrdinalIgnoreCase)
                    || (report.dependencies.Contains(path)
                        && path.EndsWith(".fbx", StringComparison.OrdinalIgnoreCase)))
                .OrderBy(path => path, StringComparer.Ordinal)
                .Select(path => InspectModel(path, report.dependencies)).ToArray();
            File.WriteAllText(arguments[index + 1], JsonUtility.ToJson(report, true));
            Debug.Log("RoboRacer scene dependency audit completed: " + report.dependencies.Length);
        }
    }
}
