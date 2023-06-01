import os


def add_implementation_envs(env, _app):

    # Add requirements to the plugin path
    pype_root = os.environ["OPENPYPE_REPOS_ROOT"]
    new_plugins_paths = [
        os.path.join(pype_root, "openpype", "hosts", "cinema4d", "startup")
    ]
    old_plugins_path = env.get("g_additionalModulePath") or ""
    for path in old_plugins_path.split(os.pathsep):
        if not path:
            continue

        norm_path = os.path.normpath(path)
        if norm_path not in new_plugins_paths:
            new_plugins_paths.append(norm_path)

    env["g_additionalModulePath"] = os.pathsep.join(new_plugins_paths)

    # Add requirements to the PYTHONPATH. Recent version of Cinema4D do not
    # add the PYTHONPATH to sys.path internally and thus require to explicitly
    # have the right pythonpaths set up with a dedicated variable.
    app_version = int(_app.name)
    print("Detected app version: {}".format(app_version))
    if app_version >= 2023:
        # C4D updated Python 3.10.8 in 2023.2
        pythonpath_key = "C4DPYTHONPATH310"
    elif app_version > 23:
        pythonpath_key = "C4DPYTHONPATH39"
    elif app_version == 23:
        pythonpath_key = "C4DPYTHONPATH37"
    else:
        # Legacy
        pythonpath_key = "PYTHONPATH"

    new_c4dpython_path = [
        os.path.join(pype_root, "vendor", "python")
    ]

    # Add any existing requirements from the c4d python path env var
    old_c4dpython_path = env.get(pythonpath_key) or ""
    for path in old_c4dpython_path.split(os.pathsep):
        if not path:
            continue

        norm_path = os.path.normpath(path)
        if norm_path not in new_plugins_paths:
            new_c4dpython_path.append(norm_path)

    # Add entries from PYTHONPATH  c4d python path
    old_python_path = env.get("PYTHONPATH") or ""
    for path in old_python_path.split(os.pathsep):
        if not path:
            continue

        norm_path = os.path.normpath(path)
        if norm_path not in new_plugins_paths:
            new_c4dpython_path.append(norm_path)

    env[pythonpath_key] = os.pathsep.join(new_c4dpython_path)

    # C4D's python ships without python3.dll which pyside expects
    if "win" in env.get("PLAT"):
        new_dll_path = [
            os.path.join(pype_root, "openpype", "hosts", "cinema4d", "resource", "windows", "bin")
        ]
    else:
        new_dll_path = []

    old_dll_path = env.get("OPENPYPE_DLL_DIRS") or ""
    for path in old_dll_path.split(os.pathsep):
        if not path:
            continue
        norm_path = os.path.normpath(path)
        if norm_path not in new_dll_path:
            new_dll_path.append(norm_path)
    env["OPENPYPE_DLL_DIRS"] = os.pathsep.join(new_dll_path)
    # Set default values if are not already set via settings
    defaults = {
        "OPENPYPE_LOG_NO_COLORS": "Yes"
    }
    for key, value in defaults.items():
        if not env.get(key):
            env[key] = value